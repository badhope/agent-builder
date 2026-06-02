# Changelog

All notable changes to DocFormatConverter are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-06-01

### Added
- Full rewrite of the original `badhope/DocFormatConverter` repository.
- FastAPI backend with async SQLAlchemy 2.0 + Alembic migrations.
- Celery worker pool for asynchronous conversions, with beat-scheduled cleanup.
- React 18 + TypeScript + Vite + Tailwind frontend.
- 40+ supported formats across documents, spreadsheets, presentations,
  markup, structured data, images, and ebooks.
- Pluggable storage layer (local FS / S3 / MinIO) with the same interface.
- Authentication: Argon2id passwords + RS256 JWT + scoped API keys.
- Magic-byte validation, optional ClamAV antivirus, path-traversal protection.
- Sandboxed subprocess execution with rlimit + setsid + wall-clock timeout.
- Rate limiting via `slowapi` + Redis (per-IP, per-user, per-route).
- HMAC-SHA256 signed webhook delivery with timestamp + replay protection.
- WebSocket progress feed via Redis pub/sub.
- Prometheus metrics, OpenTelemetry tracing, structured JSON logs.
- Full Kubernetes manifests, production docker-compose, nginx TLS config.
- CI: backend (lint + typecheck + tests + bandit), frontend (lint + typecheck + build + test),
  Docker images (ghcr.io), security scans (pip-audit, bandit, CodeQL, Trivy, TruffleHog).
- Backup/restore scripts, Let's Encrypt issuer, healthcheck, init-minio.
- Comprehensive documentation: architecture, API reference, deployment,
  security, operations, contributing.

### Changed
- **Replaced** the legacy `config.yaml` (YAML) with Pydantic v2 settings
  loaded from environment variables (12-factor).
- **Replaced** the Flask-style `gunicorn app:app` startup with
  `uvicorn app.main:app` (the original requirements.txt was self-contradictory).
- **Replaced** the `wkhtmltopdf` backend (deprecated, multiple CVEs) with
  WeasyPrint + LibreOffice + headless Chromium pathways.
- **Replaced** the unmaintained `PyPDF2` with `pypdf` and `pdfplumber`.

### Removed
- All legacy YAML configuration that hard-coded `cors_origins: "*"`,
  empty API-key enforcement, plaintext DB credentials, and missing
  rate-limit / magic-byte / antivirus checks. The original repo is
  preserved in `archive/` for reference.

### Security
- Per-user Argon2id parameters; configurable cost.
- RS256 JWT keys generated on first start, mountable in production.
- API keys stored as SHA-256 hash; prefix retained for UX.
- All API errors return stable codes and never leak internal state.
- Strict CORS allow-list (no wildcard in production).
- HSTS preload header on every response.
- Audit log of every privileged action.

[1.0.0]: https://github.com/badhope/DocFormatConverter/releases/tag/v1.0.0
