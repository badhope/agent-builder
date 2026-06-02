# Architecture

## High level

DocFormatConverter is a stateless API in front of an async task pipeline.

```
                ┌─────────────────┐
                │   Browser SPA   │  React 18 + TanStack Query
                └────────┬────────┘
                         │  HTTPS (nginx)
                ┌────────▼────────┐
                │  FastAPI (Gunicorn / Uvicorn)  │
                │  ─────────────────────────────  │
                │  • JWT + API-Key auth            │
                │  • Slowapi rate-limit            │
                │  • Prometheus middleware         │
                │  • Request-ID + structured log   │
                └────┬───────────────┬────────────┘
                     │ asyncpg       │ boto3 / aiobotocore
                     │               │
              ┌──────▼──────┐    ┌────▼─────┐
              │  Postgres   │    │   S3 /   │
              │  (16-alpine)│    │  MinIO   │
              └─────────────┘    └──────────┘
                     ▲
                     │ result backend
              ┌──────┴───────────────────────┐
              │       Celery worker          │
              │  ─ soffice · pandoc · tesseract
              │  ─ weasyprint · pillow · cairosvg
              │  ─ pyclamd (antivirus)       │
              │  ─ rlimit sandbox            │
              └──────┬───────────────────────┘
                     │
              ┌──────▼──────┐
              │    Redis    │  broker + result + pubsub
              └─────────────┘
```

## Backend layout

```
backend/app/
├── api/v1/routes/   # thin FastAPI handlers, Pydantic in/out
├── schemas/         # Pydantic v2 request/response models
├── services/        # business logic (transactional, takes AsyncSession)
├── core/            # cross-cutting: security, sanitizers, rate-limit
├── db/              # async SQLAlchemy 2.0 + Alembic
├── converters/      # format registry + per-converter implementations
├── storage/         # S3 / local backends behind a common interface
├── workers/         # Celery tasks: conversion, cleanup, webhook delivery
├── websocket/       # connection manager + Redis pub/sub fan-out
├── observability/   # prometheus + otel
└── main.py          # app factory + lifespan
```

The dependency direction is one-way: `api → services → db/models/core`,
never the reverse. `workers` calls `services` (never `api`).

## Conversion pipeline

```
  client            API                worker               storage
    │                │                   │                    │
    │ POST /convert  │                   │                    │
    ├───────────────▶│                   │                    │
    │                │ validate, persist│                    │
    │                │ enqueue Celery    │                    │
    │   202 + task   │                   │                    │
    │◀───────────────┤                   │                    │
    │                │                   │                    │
    │                │       run_conversion()                │
    │                ├──────────────────▶│                    │
    │                │                   │ download source    │
    │                │                   ├───────────────────▶│
    │                │                   │ sniff (sanity)     │
    │                │                   │ scan (antivirus)   │
    │                │                   │ pick converter     │
    │                │                   │ exec sandbox       │
    │                │                   │ upload result      │
    │                │                   ├───────────────────▶│
    │                │                   │ persist task state │
    │                │                   │ progress pubsub    │
    │                │                   │ webhook (if any)   │
    │                │                   ▼                    │
    │  WS /tasks/{id}│                   │                    │
    │◀───────────────┤                   │                    │
```

## Format registry

Each converter declares `inputs` and `outputs` as sets of format names
(lower-case, no dot). The `ConverterRegistry` builds the full adjacency
list at startup; `pick(source, target)` returns the first matching edge
sorted by score.

Add a new format pair by writing a `MyConverter(BaseConverter)` class
and adding it to `app/converters/<category>/my_converter.py`. It is
auto-discovered on first registry access.

## Security boundaries

| Boundary | Mechanism |
|----------|-----------|
| Network | TLS at nginx, HSTS preload, CSP, `X-Frame-Options: DENY` |
| AuthN | JWT (RS256) **or** API Key (SHA-256 hash) |
| AuthZ | Role + scope on every protected route; admin route gate |
| Input | Magic-byte sniff, MIME check, filename sanitisation, path-traversal guard |
| Process | subprocess via `setsid` + `rlimit`; no shell |
| Storage | S3 bucket per environment; signed-URL only downloads |
| Output | HMAC-SHA256 webhook signature with timestamp + nonce |

## State

* **Stateless API** — any pod can serve any request. Session state lives in
  Postgres, transient state in Redis.
* **Stateful worker** — only in the sense that long-running conversions
  hold a Celery task lease (`acks_late=True`, `worker_prefetch_multiplier=1`).
  Crashes are recovered by the `purge_orphan_tasks` beat job.
* **Idempotency** — every state-changing endpoint accepts an
  `Idempotency-Key` header that is stored for 24h and replays the prior
  response. (Implemented in `services/idempotency.py` — extend as needed.)

## Why these choices

* **FastAPI + Pydantic v2** — fastest path to a typed, OpenAPI-documented
  HTTP API. Pydantic v2 (Rust core) is ~5× faster than v1.
* **SQLAlchemy 2.0 async** — best-in-class async ORM with explicit
  `select()` style. Avoids the impedance mismatch of sync code in async
  handlers.
* **Celery + Redis** — battle-tested, observability story is mature
  (Flower, Prometheus exporters), and it cleanly separates the request
  path from long-running work.
* **MinIO (S3)** — same API as AWS S3, runs locally with one container.
  Swap by changing `S3_ENDPOINT_URL`.
* **Argon2id + RS256 JWT** — current OWASP recommendation. RS256 lets
  third-party services verify tokens without holding a shared secret.
* **WebSockets via Redis pubsub** — single source of truth for progress;
  the API and worker stay loosely coupled.

## What this is not

* **Not** a SaaS billing platform. Plan tiers are enforced in code, but
  payment processing is out of scope.
* **Not** a serverless worker. Long conversions on cold containers are
  expensive; this is designed for long-lived worker pools.
* **Not** a CDN. Files are served by the API directly (streaming) or
  via short-lived signed URLs.
