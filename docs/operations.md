# Operations runbook

## Health checks

| Endpoint | What it does | When to use |
|----------|--------------|-------------|
| `GET /healthz` | Lightweight liveness probe. Always 200 unless the process is wedged. | K8s `livenessProbe`, Docker `HEALTHCHECK` |
| `GET /readyz` | Deep readiness. Checks DB + storage. Returns 200 only if both healthy. | K8s `readinessProbe`, load balancer |
| `GET /metrics` | Prometheus exposition. | Scrape every 15s |

## Common incidents

### "Queue is backing up"

```promql
sum by (queue) (docconv_queue_depth) > 1000
```

1. Check `kubectl get pods -l app=docconv-worker` — are workers healthy?
2. `kubectl logs -l app=docconv-worker --tail=200` — what are they stuck on?
3. Scale workers: `kubectl scale deploy/docconv-worker --replicas=16`
4. If the issue is "stuck task", cancel the head of the queue:
   `docker exec api python -m app.scripts.purge_stuck`

### "5xx rate is spiking"

```promql
sum(rate(docconv_http_requests_total{status=~"5.."}[5m]))
  / sum(rate(docconv_http_requests_total[5m])) > 0.05
```

1. Open Grafana → DocFormatConverter dashboard → check the
   "Latency p50/p95/p99" panel for slow routes.
2. `kubectl logs -l app=docconv-api --tail=300 | grep '"level":"error"'`
3. If a single deployment is hot, drain & restart: `kubectl rollout restart deploy/docconv-api`

### "Antivirus quarantines are spiking"

1. Check the ClamAV server is reachable: `docker exec worker clamdscan --ping`
2. If the database has false positives, mark the signature as
   allow-listed in the `antivirus_allowlist` table.
3. To temporarily fail-open: `ANTIVIRUS_ENABLED=0 kubectl rollout restart deploy/docconv-worker`

### "Database is full"

1. Check the conversion table is being trimmed:
   `SELECT count(*) FROM tasks WHERE created_at < now() - interval '7 days';`
2. `cleanup_old_tasks` beat job (default: every 6h) should be purging.
3. Manually trigger: `docker exec api python -m app.scripts.purge --older-than 24h`
4. If it keeps recurring, increase disk or reduce `MAX_RETENTION_DAYS`.

### "Need to rotate the JWT key"

```bash
# Generate new keys alongside the old ones
docker exec api python -m app.scripts.generate_jwt_keys --force
# Trigger a rolling restart so the new private key is loaded
kubectl rollout restart deploy/docconv-api deploy/docconv-worker
# Old refresh tokens stay valid until their own expiry (≤ 30 days)
```

### "Need to revoke an API key"

```bash
docker exec api python -m app.scripts.revoke_api_key <key_id>
```

Or via the API: `DELETE /v1/auth/api-keys/{id}`.

## Backups

* Nightly via `deploy/scripts/backup.sh`, offloaded to S3/Glacier.
* Test restores quarterly with `deploy/scripts/restore.sh`.
* Postgres logical dumps + MinIO snapshots are independent — you
  only need to restore what was lost.

## Observability

* **Logs**: structured JSON to stdout, scraped by your log shipper
  (Loki, Vector, Fluent Bit). Filter by `request_id` to trace one
  request across the API, the worker, and the storage.
* **Metrics**: Prometheus pulls `/metrics` from every pod. The
  included Grafana dashboard (`deploy/grafana/dashboards/api.json`)
  gives you request rate, latency, error rate, queue depth, and
  conversion throughput.
* **Traces**: OpenTelemetry SDK is wired up. Set
  `OTEL_EXPORTER_OTLP_ENDPOINT` to enable. Out of the box, traces
  are recorded but not exported.

## Capacity

* **DB connections**: pool size = `DB_POOL_SIZE` (default 10 per
  pod). The HPA target is 70% CPU, so expect ≈ 30 connections per
  1000 rps.
* **Worker memory**: each concurrent task uses ~200 MiB while
  LibreOffice is running. A 4-concurrency worker on a 4 GiB pod is
  the sweet spot.
* **MinIO disk**: budget `4 × avg_file_size × daily_uploads`.

## Maintenance windows

All upgrades are zero-downtime (rolling update with `maxUnavailable: 0`).
The only exception is a breaking schema change — these always ship with
both an Alembic migration and a one-epoch compatibility shim so the old
API can still run while you drain traffic to the new one.
