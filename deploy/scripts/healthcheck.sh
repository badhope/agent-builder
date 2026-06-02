#!/usr/bin/env bash
# Wait for the API to be ready, then call /healthz and /readyz.
set -euo pipefail
API="${API:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-60}"

i=0
while [ "$i" -lt "$TIMEOUT" ]; do
  if curl -fsS "${API}/healthz" >/dev/null 2>&1; then
    echo "[healthcheck] /healthz OK"
    if curl -fsS "${API}/readyz" >/dev/null 2>&1; then
      echo "[healthcheck] /readyz OK"
      exit 0
    else
      echo "[healthcheck] /readyz not ready yet"
    fi
  fi
  sleep 1
  i=$((i+1))
done

echo "[healthcheck] timed out" >&2
exit 1
