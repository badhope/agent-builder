# Deployment

DocFormatConverter is designed to run anywhere Docker can run.

## 1. Local (docker-compose, single host)

The fastest way to get a full stack going.

```bash
git clone https://github.com/badhope/DocFormatConverter.git
cd DocFormatConverter
cp .env.example .env
$EDITOR .env                        # set POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD, BOOTSTRAP_ADMIN_*
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml run --rm api bootstrap-admin
open http://localhost:5173           # frontend
```

To deploy with the production compose file (everything behind nginx):

```bash
docker compose up -d --build
```

## 2. Single host with TLS (docker-compose + nginx + Let's Encrypt)

```bash
git clone …
cp .env.example .env && $EDITOR .env
docker compose up -d --build
EMAIL=you@example.com DOMAIN=convert.example.com ./deploy/scripts/issue-cert.sh
docker compose restart nginx
```

`issue-cert.sh` writes the cert to `/etc/nginx/certs/`, configures auto-renew
via cron, and reloads nginx.

## 3. Kubernetes (manifests in `deploy/k8s/`)

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl create secret generic docconv-secrets \
  --from-literal=POSTGRES_PASSWORD=$(openssl rand -hex 32) \
  --from-literal=S3_ACCESS_KEY=$(openssl rand -hex 16) \
  --from-literal=S3_SECRET_KEY=$(openssl rand -hex 32) \
  --from-literal=BOOTSTRAP_ADMIN_PASSWORD=$(openssl rand -hex 16) \
  --from-literal=SECRET_KEY=$(openssl rand -hex 64) \
  -n docformatconverter
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/pvc.yaml
kubectl apply -f deploy/k8s/api-deployment.yaml
kubectl apply -f deploy/k8s/worker-deployment.yaml
kubectl apply -f deploy/k8s/beat-deployment.yaml
kubectl apply -f deploy/k8s/ingress.yaml
```

Tear down:

```bash
kubectl delete namespace docformatconverter
```

## 4. Helm

A first-party Helm chart is on the roadmap. Until then, the Kustomize
overlay at `deploy/k8s/` is the supported way to install in clusters.

## Environment variables

See `.env.example` for the full set. Most important:

| Var | Default | Notes |
|-----|---------|-------|
| `APP_ENV` | `dev` | `dev` / `staging` / `prod` |
| `SECRET_KEY` | _required_ | ≥ 64 random bytes; rotate quarterly |
| `DATABASE_URL` | _required_ | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | _required_ | `redis://host:6379/0` |
| `CELERY_BROKER_URL` | _required_ | `redis://host:6379/1` |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `S3_ENDPOINT_URL` | _empty_ | `https://s3.amazonaws.com` or `http://minio:9000` |
| `S3_BUCKET` | `docconv` | |
| `CORS_ALLOW_ORIGINS` | `[]` | JSON list; required in production |
| `MAX_FILE_SIZE` | `104857600` (100 MiB) | per-upload cap |
| `RATE_LIMIT_DEFAULT` | `120/minute` | |
| `ANTIVIRUS_ENABLED` | `0` | `1` to require ClamAV |
| `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` | _empty_ | bootstrap on first start |

## Capacity planning

* **API**: 1 vCPU / 512 MiB per replica is enough for 200 req/s
* **Worker**: 1 vCPU / 1 GiB per concurrency. A 4-concurrency worker can
  sustain ~30 PDF→PNG conversions per minute
* **Postgres**: 100 GB allocated for 10 million conversion records
* **MinIO**: 4× the average file size × peak daily uploads
* **Redis**: small; mostly metadata. 2 GB is plenty for 1k rps

## Backups

`deploy/scripts/backup.sh` ships a timestamped tarball containing:

* `postgres.dump` — `pg_dump -Fc`
* `minio.tar.gz` — full bucket snapshot
* `jwt_private.pem` — only if mounted in the same volume
* `manifest.json`

Upload to S3/Glacier with the rest of your backup pipeline.

## Restore

```bash
./deploy/scripts/restore.sh /var/backups/docconv/20260101T000000Z.tar.gz
```

## Upgrades

1. `docker compose pull`
2. `docker compose up -d api worker beat` (rolling restart)
3. Migrations run automatically on API boot
4. Smoke-test `/readyz` and a sample conversion

Roll back the same way: `docker compose pull <previous-tag> && up -d`.
