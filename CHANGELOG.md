# Changelog

All notable changes are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### In progress
- WebSocket progress for the mini-program task-detail page (branch
  `feature/mp-ws`).
- Real antivirus integration. Right now `core/antivirus.py` returns
  "clean" for everything. ClamAV is the likely backend, but it adds
  ~600MB to the worker image and I haven't measured the latency hit.
- Per-tenant rate limits. The current limiter is global.

## [0.3.0] - 2026-06-02

### Added
- WeChat mini-program via Taro 3.6. Compiles to weapp, h5, and alipay
  from a single codebase.
- WS endpoint for live task progress. Used by the web frontend; the
  mini-program is still polling.
- Email verification + TOTP 2FA + password reset. All three were
  requested by the same person, who is now the only user that uses
  any of them. Whatever, it's done.
- Per-user API keys, with a 32-char prefix shown once and a SHA-256
  hash stored in the DB.
- Webhook delivery with HMAC-SHA256 signatures and exponential
  backoff (1m, 5m, 30m, 2h, 12h, 24h, then dead-letter).
- Batch conversion: zip up to 200 files in one request.
- Idempotency keys on POST /convert. Same key returns the same task,
  no duplicate work.

### Changed
- Storage: now uses streaming uploads (`StreamingResponse`) instead of
  buffering whole files in memory. Old code OOM'd on a 4GB PDF.
- JWT: switched from HS256 to RS256. The shared-secret setup was
  fine in the single-service days but the moment we added a second
  replica, the secrets got out of sync in a way I don't want to debug
  again.
- Scheduler: Croner is gone, replaced by APScheduler. The cron syntax
  was the same but the threading model was less surprising.

### Fixed
- Cleanup worker was hard-deleting user-requested soft deletes. Added
  a `deleted_reason` column and only purge rows where the reason is
  `retention_elapsed` past the grace period. (See commit history;
  this was the bug that almost nuked a real user's data.)
- The `/v1/formats` endpoint used to recompute the full graph on
  every call. Cached in Redis with a 5-minute TTL, invalidated on
  converter registration.
- `useTaskProgress` no longer hammers the server on reconnect: it
  waits for the next natural tick. Tiny fix, real impact on a flaky
  network.

## [0.2.0] - 2026-04-15

### Added
- Frontend: React + Vite + Tailwind, replacing the original Vue 3
  prototype. Faster HMR, better TS story.
- WebSocket progress replaced the old "refresh the page" UX.
- Storage backend: MinIO for dev, S3 for prod. Same interface.

### Removed
- Vue 3 prototype. Not in git history, just gone.

## [0.1.0] - 2026-02-01

First version that anyone other than me used. It converted PDFs to
DOCX and that was it. Still in a private repo; some of those code
paths survive in `converters/document/pdf_converter.py`.
