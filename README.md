# DocFormatConverter

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](.github/workflows)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![Node](https://img.shields.io/badge/Node-20-339933)

A secure, production-grade **multi-format document conversion** platform.

Convert documents, spreadsheets, presentations, images, ebooks and structured
data between **40+ formats** with batch processing, async task tracking,
webhook callbacks, JWT & API-Key auth, magic-byte validation, antivirus
scanning, and real-time progress over WebSockets.

* **Backend** — FastAPI · Python 3.12 · SQLAlchemy 2.0 async · Celery · PostgreSQL · Redis · MinIO
* **Frontend** — React 18 · TypeScript · Vite · Tailwind CSS · TanStack Query
* **Workers** — Celery + beat, runs LibreOffice, Pandoc, Tesseract, WeasyPrint, Pillow, Pillow-HEIF
* **Storage** — S3-compatible (MinIO in dev) or local filesystem, swappable via config
* **Security** — Argon2id, RS256 JWT, scoped API keys, HMAC-signed download tokens, CSP, HSTS, rate limiting, audit log

---

## Features

| Category | Formats | Backends |
|----------|---------|----------|
| Documents | PDF · DOCX · ODT · RTF · EPUB · TXT | LibreOffice · Pandoc · WeasyPrint |
| Spreadsheets | XLSX · XLS · CSV · ODS | LibreOffice · openpyxl · pandas |
| Presentations | PPTX · PPT · ODP | LibreOffice · python-pptx |
| Markup | Markdown · HTML · LaTeX | Pandoc · WeasyPrint · markdown-it |
| Structured | JSON · YAML · XML · CSV | Native parsers + jsonschema |
| Images | PNG · JPG · WEBP · BMP · TIFF · SVG · HEIC | Pillow · Pillow-HEIF · CairoSVG · ImageMagick |
| Ebooks | EPUB · MOBI · AZW3 | Pandoc · EbookLib |
| OCR | Images → TXT / PDF (searchable) | Tesseract |

* Async tasks with priority queue
* Batch API (one batch, many files)
* Webhook callbacks with HMAC-SHA256 signatures
* Real-time progress over WebSockets
* Per-user quotas & plan tiers (free / pro / enterprise)
* Idempotency keys
* Auto-expiry & garbage collection of outputs
* Prometheus metrics, OpenTelemetry tracing, structured JSON logs
* Full Kubernetes manifests + production docker-compose

---

## Quick start (Docker)

```bash
git clone https://github.com/badhope/DocFormatConverter.git
cd DocFormatConverter
cp .env.example .env
docker compose -f docker-compose.dev.yml up
```

The frontend is available at <http://localhost:5173>, the API at
<http://localhost:8000/docs>.

Bootstrap the first admin user:

```bash
docker compose -f docker-compose.dev.yml run --rm api bootstrap-admin
```

Create an API key for scripting:

```bash
docker compose -f docker-compose.dev.yml run --rm api create-api-key admin@example.com
```

---

## Local development (without Docker)

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m app.scripts.generate_jwt_keys
alembic -c backend/alembic.ini upgrade head
uvicorn app.main:app --reload

# Worker (separate terminal)
celery -A app.workers.celery_app worker -l info -Q conversions,webhooks,maintenance

# Beat (separate terminal)
celery -A app.workers.celery_app beat -l info

# Frontend
cd frontend
npm install
npm run dev
```

---

## API at a glance

```http
POST   /v1/auth/register
POST   /v1/auth/login          # { access_token, refresh_token }
POST   /v1/auth/refresh
GET    /v1/auth/me

POST   /v1/files/uploads       # multipart/form-data
GET    /v1/files/{id}
GET    /v1/files/{id}/download
GET    /v1/files/{id}/signed-url

POST   /v1/convert             # { source_file_id, target_format }
POST   /v1/convert/sync        # small files only
POST   /v1/batches             # batch with N file_ids

GET    /v1/tasks
GET    /v1/tasks/{id}
GET    /v1/tasks/{id}/logs
POST   /v1/tasks/{id}/cancel
POST   /v1/tasks/{id}/retry

WS     /ws/tasks/{id}          # progress stream
```

Authentication:

```bash
# JWT
curl -H "Authorization: Bearer $TOKEN" https://api.example.com/v1/tasks

# API Key
curl -H "X-API-Key: dck_..."   https://api.example.com/v1/tasks
```

Full reference: [docs/api.md](docs/api.md).

---

## Architecture

```
        ┌──────────────┐
        │   Browser    │
        └──────┬───────┘
               │ HTTPS
        ┌──────▼───────┐
        │     Nginx    │  TLS, rate-limit, gzip, security headers
        └──────┬───────┘
               │
   ┌───────────┴───────────┐
   │                       │
┌──▼─────────┐      ┌──────▼──────┐
│ React SPA  │      │  FastAPI    │  ── asyncpg ──▶  Postgres
│ (nginx)    │      │  (uvicorn)  │  ── redis  ──▶  Redis (broker + pubsub)
└────────────┘      └──────┬──────┘  ── boto3  ──▶  MinIO / S3
                           │
                  ┌────────┴────────┐
                  │  Celery worker  │  ── soffice · pandoc · tesseract · weasyprint
                  └────────────────┘
                  ┌────────────────┐
                  │  Celery beat   │  ── expiry · cleanup · webhook retries
                  └────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for the full picture.

---

## Repository layout

```
DocFormatConverter/
├── backend/                     # FastAPI app
│   ├── app/
│   │   ├── api/v1/routes/      # auth, files, convert, tasks, batches, ...
│   │   ├── converters/          # converter registry + backends + per-format impls
│   │   ├── core/                # security, magic_bytes, sanitizers, rate_limit
│   │   ├── db/models/           # SQLAlchemy 2.0 async models
│   │   ├── observability/       # prometheus + otel
│   │   ├── schemas/             # Pydantic v2 request/response models
│   │   ├── services/            # business logic
│   │   ├── storage/             # S3 + local adapters
│   │   ├── workers/             # Celery tasks
│   │   ├── websocket/           # WS manager + pubsub
│   │   └── main.py              # app factory + lifespan
│   ├── alembic/                 # migrations
│   └── tests/                   # pytest + httpx
├── frontend/                    # React + TS + Vite + Tailwind
│   ├── src/{pages,components,stores,api,hooks,i18n,utils,types}
│   ├── Dockerfile
│   └── nginx.conf
├── deploy/
│   ├── nginx/                   # TLS termination config
│   ├── prometheus/              # scrape + alert rules
│   ├── grafana/                 # datasource + dashboard provisioning
│   ├── k8s/                     # Deployment / Service / Ingress / HPA / PVC
│   └── scripts/                 # backup / restore / cert / healthcheck
├── entrypoints/                 # container entrypoint (migrate, api, worker, beat)
├── docs/                        # architecture · api · deployment · security · operations
├── .github/workflows/           # CI: backend, frontend, docker, security
├── pyproject.toml               # backend tooling + deps
├── Makefile                     # dev shortcuts
└── docker-compose.yml           # production stack
```

---

## Security

DocFormatConverter follows OWASP recommendations:

* **Passwords**: Argon2id (time=3, memory=64MiB, parallelism=4) with per-user salt
* **JWT**: RS256 (asymmetric) — private key in `/app/keys/`, public key for verifiers
* **API Keys**: `dck_live_<32 random bytes>`, stored as SHA-256 hash, prefix kept for UX
* **Magic bytes**: every upload is sniffed with `filetype` + custom text heuristic; MIME mismatch → 415
* **Path traversal**: every filename sanitized; downloads `safe_join`'d
* **Antivirus**: optional ClamAV scan before conversion (configurable fail-open/fail-closed)
* **Rate limit**: per-IP + per-user token-bucket via `slowapi` + Redis
* **CSP / HSTS / Referrer-Policy / X-Frame-Options** on every response
* **CORS**: allow-list of origins (no `*` in production)
* **Webhook signatures**: HMAC-SHA256 with replay protection (timestamp in header)
* **Audit log**: every privileged action written to `audit_log` (admin-only GET)

See [docs/security.md](docs/security.md) for the full threat model and
hardening checklist.

---

## Operations

* **Backups**: `deploy/scripts/backup.sh` — Postgres logical dump + MinIO snapshot
* **Restore**: `deploy/scripts/restore.sh <archive.tar.gz>`
* **Health**: `/healthz` (liveness) and `/readyz` (deep, with DB + storage checks)
* **Metrics**: `/metrics` (Prometheus exposition)
* **Logs**: structured JSON to stdout, scraped by Loki/Vector
* **Alerts**: see `deploy/prometheus/rules/docconv.yml`
* **Migrations**: `alembic -c backend/alembic.ini upgrade head` (auto-run on API boot)

---

## Documentation

* [Architecture](docs/architecture.md)
* [API reference](docs/api.md)
* [Deployment](docs/deployment.md) — Docker · Compose · Kubernetes · Helm
* [Security](docs/security.md) — threat model · hardening · compliance notes
* [Operations](docs/operations.md) — runbook · metrics · backups

---

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

Built on the shoulders of giants: FastAPI, SQLAlchemy, Celery, React, Vite,
Tailwind, LibreOffice, Pandoc, Tesseract, WeasyPrint, Pillow, Argon2-cffi,
PyJWT, structlog, and many others. See `pyproject.toml` for the full list.
