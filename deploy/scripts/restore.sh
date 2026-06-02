#!/usr/bin/env bash
# Restore a backup tarball.
#
# Usage: ./deploy/scripts/restore.sh /var/backups/docconv/20260101T000000Z.tar.gz
set -euo pipefail

ARCHIVE="${1:-}"
if [ -z "${ARCHIVE}" ] || [ ! -f "${ARCHIVE}" ]; then
  echo "Usage: $0 <archive.tar.gz>" >&2
  exit 1
fi

WORK="$(mktemp -d)"
tar xzf "${ARCHIVE}" -C "${WORK}"
TIMESTAMP_DIR="$(ls "${WORK}")"
SRC="${WORK}/${TIMESTAMP_DIR}"

echo "[restore] source=${SRC}"

if [ -f "${SRC}/postgres.dump" ]; then
  echo "[restore] loading postgres dump…"
  cat "${SRC}/postgres.dump" | docker exec -i docformatconverter-postgres-1 \
    pg_restore -U "${POSTGRES_USER:-docconv}" -d "${POSTGRES_DB:-docconv}" --clean --if-exists
fi

if [ -f "${SRC}/minio.tar.gz" ]; then
  echo "[restore] restoring MinIO data…"
  docker run --rm \
    -v docformatconverter_minio_data:/data \
    -v "${SRC}:/backup:ro" \
    alpine sh -c "rm -rf /data/* && tar xzf /backup/minio.tar.gz -C /data"
fi

if [ -f "${SRC}/jwt_private.pem" ]; then
  echo "[restore] restoring JWT key…"
  install -m 0600 "${SRC}/jwt_private.pem" \
    /var/lib/docker/volumes/docformatconverter_jwt_keys/_data/jwt_private.pem
  # Generate matching public key from it
  openssl rsa -in /var/lib/docker/volumes/docformatconverter_jwt_keys/_data/jwt_private.pem \
    -pubout -out /var/lib/docker/volumes/docformatconverter_jwt_keys/_data/jwt_public.pem
fi

rm -rf "${WORK}"
echo "[restore] complete"
