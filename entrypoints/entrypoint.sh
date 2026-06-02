#!/usr/bin/env bash
# Entrypoint: run migrations, then exec the requested command.
set -euo pipefail

cmd="${1:-api}"

echo "[entrypoint] CMD=${cmd} APP_ENV=${APP_ENV:-dev}"

# Generate JWT key pair on first start (only if keys are missing).
if [ ! -f "${JWT_KEYS_DIR:-/app/keys}/jwt_private.pem" ] && [ "${SKIP_KEYGEN:-0}" != "1" ]; then
  echo "[entrypoint] generating JWT key pair…"
  python -m app.scripts.generate_jwt_keys
fi

case "${cmd}" in
  api)
    echo "[entrypoint] applying DB migrations…"
    alembic -c backend/alembic.ini upgrade head || {
      echo "[entrypoint] alembic upgrade failed" >&2
      exit 1
    }
    echo "[entrypoint] starting API…"
    if [ "${APP_ENV:-prod}" = "dev" ]; then
      exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --proxy-headers
    else
      exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
    fi
    ;;
  worker)
    echo "[entrypoint] starting Celery worker…"
    exec celery -A app.workers.celery_app worker \
      --loglevel="${CELERY_LOG_LEVEL:-INFO}" \
      --concurrency="${CELERY_CONCURRENCY:-4}" \
      -Q "${CELERY_QUEUES:-conversions,webhooks,maintenance}"
    ;;
  beat)
    exec celery -A app.workers.celery_app beat \
      --loglevel="${CELERY_LOG_LEVEL:-INFO}"
    ;;
  flower)
    exec celery -A app.workers.celery_app flower \
      --broker="${CELERY_BROKER_URL}" \
      --basic_auth="${FLOWER_USER:-admin}:${FLOWER_PASSWORD:-admin}"
    ;;
  migrate)
    alembic -c backend/alembic.ini upgrade head
    ;;
  bootstrap-admin)
    python -m app.scripts.bootstrap_admin
    ;;
  create-api-key)
    shift
    exec python -m app.scripts.create_api_key "$@"
    ;;
  generate-keys)
    python -m app.scripts.generate_jwt_keys
    ;;
  shell)
    exec python
    ;;
  *)
    exec "$@"
    ;;
esac
