# Operations

What runs in production, what I'd change, what I haven't done.

## Stack

- 3x API pods (1 vCPU / 1GB each, autoscaling on CPU > 60%)
- 4x worker pods (2 vCPU / 4GB each)
- 1x beat pod (for Celery scheduled tasks)
- Postgres 16, single primary, 1 replica for reads (manual failover)
- Redis 7, single node (we lose scheduled jobs on restart, but those
  re-fire on the next cleanup cycle so it doesn't matter)
- MinIO distributed (4 nodes, 2 disks each, erasure coding)
- nginx ingress, Let's Encrypt certs via cert-manager

## Backups

- Postgres: pg_dump every 6h, retained 14 days, offsite-rsynced
- MinIO: `mc mirror` daily to a separate bucket, 30-day retention
- JWT private key: backed up to a separate secret manager (1Password
  team vault). If you lose this, all user sessions die. Documented
  in the incident runbook.

Restoring from backup takes about 35 minutes for Postgres and 2-3
hours for MinIO. Tested quarterly.

## Monitoring

- Prometheus scrapes the API, workers, and Postgres. Grafana
  dashboards in `deploy/grafana/`.
- Sentry for backend exceptions. It's noisy on the worker side because
  LO/Pandoc exit codes don't always parse cleanly, so I have a
  `ignore_loggers` config for the most common ones.
- Alerts fire to a Telegram bot (yes, Telegram; we don't use Slack).
  On-call rotation is just me.

## Alerts that actually fire

In rough order of "this is useful" → "this is noise":

1. **Disk > 80% on MinIO nodes.** Has saved us twice. MinIO will
   refuse writes at 95%.
2. **Worker queue depth > 200 for 5m.** Means we're falling behind.
   Usually cleared in 10-15 min; if it persists, scale workers.
3. **API p99 > 2s for 5m.** Either Postgres is unhealthy or a single
   endpoint is being abused.
4. **Postgres replication lag > 30s.** Has never fired, but it's there
   because losing the read replica during a backup is bad.
5. **Cert expiring in 14 days.** Paging me 14 days before, again at
   3 days, again at 1 day. We use cert-manager so this is more of a
   sanity check than a real risk.
6. **API pod OOM killed.** The 1GB limit is tight; I bump to 2GB
   before the next release.
7. **Celery worker idle > 30m.** False alarm 90% of the time
   (overnight, weekends). I should silence it.

## Things I know I should do

- [ ] Migrate secrets from .env files to Vault. We have one prod env,
      so the bar is low. Doing it "right" needs a Vault cluster and
      someone to maintain it. On the list for after the next round
      of funding.
- [ ] Set up log-based metrics. Right now logs go to stdout, Loki
      scrapes them, and I search in Grafana when something is broken.
      A handful of pre-built queries (5xx rate by endpoint, top 10
      user errors) would speed up triage.
- [ ] Replace the custom scheduler with Celery Beat's. I have
      `app.workers.celery_app.py` configured for it but the actual
      `beat_schedule` is still in the crontab on the beat pod. Works
      fine, just inelegant.
- [ ] Add a status page. The two times we had outages, the only
      signal was the Telegram bot. A public status page is on the
      "eventually" list.

## Incident postmortems

- **2026-05-18, ~30 min downtime.** A config push to the API set
  `REDIS_URL` to the wrong host. Workers couldn't enqueue, queued
  tasks stalled, the queue-depth alert fired 4 minutes in. Rollback
  via the previous git tag. The root cause was a missing pre-commit
  hook that should have caught the wrong host; added the hook the
  next day.
- **2026-04-02, ~2 hours of degraded performance.** LibreOffice
  silently updated on the worker image and the new version crashed
  on a particular PDF. Pinned the version in the Dockerfile, added
  a smoke test (`tests/test_lo_profile_pool.py`) that converts a
  known-ugly PDF. The fix took 30 minutes; the smoke test took
  another 2 hours, and would have caught it.
- **2026-02-11, silent data loss.** Cleanup worker hard-deleted
  files that were soft-deleted by a user action (not by retention).
  Lost a real user's batch of 47 files. They were a friend, and
  gracious about it, and I shipped a fix the same day. See
  CHANGELOG for the technical details. The lesson: never delete data
  on a retention cron without a "reason" column.

## Capacity planning

Last load test, May 2026: 200 concurrent conversions of mixed types
(70% PDF→DOCX, 20% DOCX→PDF, 10% image conversions) for 30 minutes.
The system held up, with queue depth peaking at ~150 and worker
CPU at ~80%. Above that, LibreOffice starts failing with "profile
locked" errors, which is a temp-dir issue I haven't fixed.

I have not stress-tested the API separately. My guess is it would
hold up to 5-10x the load because it's mostly JSON and DB calls.
