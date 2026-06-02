#!/usr/bin/env bash
# Create the MinIO bucket used by the API if it doesn't exist.
set -euo pipefail

ENDPOINT="${S3_ENDPOINT_URL:-http://localhost:9000}"
BUCKET="${S3_BUCKET:-docconv}"
ACCESS="${S3_ACCESS_KEY:-minioadmin}"
SECRET="${S3_SECRET_KEY:-minioadmin}"

docker run --rm \
  -e MC_HOST_local="http://${ACCESS}:${SECRET}@${ENDPOINT#http://}" \
  minio/mc mb -p "local/${BUCKET}" 2>/dev/null || true
docker run --rm \
  -e MC_HOST_local="http://${ACCESS}:${SECRET}@${ENDPOINT#http://}" \
  minio/mc anonymous set none "local/${BUCKET}"

echo "[minio-init] bucket=${BUCKET} endpoint=${ENDPOINT} ready"
