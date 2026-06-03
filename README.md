# DocFormatConverter

A document-conversion platform I've been building. Web UI + REST API + WeChat
mini-program from a single Python backend. Started as a personal tool, grew
into something a few teammates started using, so I tightened it up.

The reason for the WeChat/H5/Alipay version is that most users in our context
aren't on desktop. Sharing a converted file via a tiny client is way more
useful than asking them to log into a website.

## What works

- Auth: email + password, JWT (access/refresh), email verify, TOTP 2FA, password reset
- Files: upload, scan, store, stream back. S3/MinIO in prod, local disk in dev
- Conversion: ~20 source/target pairs across document, spreadsheet, image, data
- Backends used: LibreOffice, Pandoc, Pillow, WeasyPrint, Tesseract OCR
- Batch: zip up to 200 files, get one zip back
- Webhooks: HMAC-signed callbacks when a task finishes
- Rate limit, audit log, idempotency keys
- WebSocket for live progress
- i18n (zh/en) on the web side

## Quick start (Docker, fastest)

```bash
cp .env.example .env
cp backend/.env.example backend/.env   # if present; otherwise backend reads from .env at repo root
make keys       # generates keys/jwt_{private,public}.pem
docker compose -f docker-compose.dev.yml up -d
```

API on `:8000`, web on `:5173`, MinIO console on `:9001` (minio/minio123).

## Quick start (local Python)

If you don't want Docker:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# start postgres + redis separately, or use docker compose just for those:
docker compose -f docker-compose.dev.yml up -d postgres redis minio
alembic -c backend/alembic.ini upgrade head
python -m backend.app.scripts.bootstrap_admin
uvicorn app.main:app --reload --app-dir backend
```

For the worker:

```bash
celery -A app.workers.celery_app worker -l info --app=app.workers.celery_app -C 2
```

## Repo layout

```
backend/    FastAPI + Celery
frontend/   React + Vite + Tailwind + Zustand
miniprogram/  Taro (compiles to weapp / h5 / alipay)
deploy/     nginx, prometheus, grafana, k8s
docker-compose*.yml
Makefile
```

## API surface

- `POST /v1/auth/{register,login,refresh,logout}`
- `POST /v1/auth/password-reset/{request,confirm}`
- `POST /v1/auth/email-verify/{request,confirm}`
- `POST /v1/auth/totp/{setup,verify,disable}`
- `GET  /v1/users/me`, `PATCH /v1/users/me`
- `POST /v1/files/uploads`, `GET /v1/files/{id}`, `GET /v1/files/{id}/download`
- `POST /v1/convert`, `GET /v1/tasks/{id}`, `POST /v1/tasks/{id}/{retry,cancel}`
- `POST /v1/batches`, `GET /v1/batches/{id}`
- `GET  /v1/formats`  (full graph, frontend uses this to build the format picker)
- `POST /v1/webhooks`, etc.
- `WS   /v1/ws/tasks/{id}` for progress

OpenAPI at `/docs` in dev.

## Things I left rough

A list so I don't forget, in priority order:

- `backend/app/converters/image/image_converter.py` — EXIF orientation handling
  for CMYK TIFF input is patchy. PIL flips it, then we re-encode, sometimes
  the alpha channel is dropped. Tested on a known-bad scan and got wrong colors.
  TODO: route through a `pillow` helper that strips profiles first.
- `backend/app/workers/cleanup.py:zombie_requeue` — there's a race where two
  workers both see the same zombie and both re-enqueue it. Idempotency key on
  the task would fix this, but right now we just rely on the dedup window in
  the dispatcher. Acceptable for now, not for a million tasks/day.
- `backend/app/services/result_cache.py` — Redis cache for completed tasks.
  Hit rate is good in the common case (user re-downloads), but the TTL
  refresh on read is off-by-one. Need to fix and add a metric.
- `backend/app/converters/document/docx_converter.py:to_pdf` — falls back to
  LibreOffice when pandoc can't render embedded SVGs. The LO path is
  ~5x slower. Not worth optimizing until we hit >100 PDF req/min.
- `backend/app/api/v1/routes/convert.py` — accepts `target_format` from query
  string, but a few clients send it in the body. The OpenAPI spec says query
  only, but we tolerate body. Pick one. (Issue: #14 in my head, not a real one)
- Frontend `useTaskProgress` reconnects on close but doesn't back off
  exponentially. Cheap to fix, just haven't.
- Mini-program: progress bar in `task-detail` is not yet bound to the WS
  channel — we still poll. WS is wired up in `api/client.ts` and `stores/auth.ts`
  but the task page falls back to the REST endpoint. PR ready in `feature/mp-ws`.

If you spot a real bug not in this list, please open an issue.

## Tests

```bash
make test               # full suite
make test-fast          # skip integration
cd frontend && pnpm test
```

I aim for ~80% on the backend. The converter layer is the lowest coverage
because most of the work is shelling out, which a unit test can't really
cover without a 200MB LibreOffice fixture.

## Security notes

- JWT signed with RS256. Private key never leaves the API host.
- File uploads: magic-byte sniff before any processing. The antivirus
  scanner is a stub (no ClamAV in dev) — wire it up via `core/antivirus.py`.
- API keys use a 32-char random prefix + SHA-256 hash. Constant-time
  compare in `core/security.py`.
- All outgoing webhook URLs are SSRF-checked against the private/loopback
  ranges in `core/ssrf.py`.
- CORS is locked to the configured origins, not `*`.

## Performance

Numbers from `make load-smoke` on my laptop (16 cores, NVMe, no GPU):

- PDF → DOCX: ~1.8s/10MB
- DOCX → PDF: ~2.4s/10MB
- PNG → WebP:  ~40ms/2MB
- CSV → XLSX:  ~120ms/100k rows

Workers autoscale by `celery_queue_length` in K8s; the Helm chart is in
`deploy/k8s/`.

## License

MIT. See `LICENSE`.

## Contact

Open an issue. I read them.

— [@badhope](https://github.com/badhope)
