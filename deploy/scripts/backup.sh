#!/usr/bin/env bash
# Back up Postgres + MinIO to a timestamped tarball.
#
# Usage: BACKUP_DIR=/var/backups/docconv ./deploy/scripts/backup.sh
#
# Restores via ./deploy/scripts/restore.sh.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/docconv}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_DIR}/${TIMESTAMP}"
mkdir -p "${DEST}"

echo "[backup] target=${DEST}"

# Postgres
echo "[backup] dumping postgres…"
docker exec docformatconverter-postgres-1 \
  pg_dump -U "${POSTGRES_USER:-docconv}" -Fc "${POSTGRES_DB:-docconv}" \
  > "${DEST}/postgres.dump"

# MinIO data (read-only snapshot via mc mirror)
echo "[backup] mirroring MinIO bucket…"
docker run --rm \
  -v docformatconverter_minio_data:/data:ro \
  -v "${DEST}:/backup" \
  alpine sh -c "tar czf /backup/minio.tar.gz -C /data ."

# JWT keys (only if mounted in the same volume)
if [ -f "/var/lib/docker/volumes/docformatconverter_jwt_keys/_data/jwt_private.pem" ]; then
  cp /var/lib/docker/volumes/docformatconverter_jwt_keys/_data/jwt_private.pem \
     "${DEST}/jwt_private.pem"
fi

# Manifest
cat > "${DEST}/manifest.json" <<JSON
{
  "timestamp": "${TIMESTAMP}",
  "components": ["postgres", "minio", "jwt_keys"],
  "version": "1.0.0"
}
JSON

# Final tarball
cd "${BACKUP_DIR}"
tar czf "${TIMESTAMP}.tar.gz" "${TIMESTAMP}"
rm -rf "${TIMESTAMP}"
echo "[backup] complete: ${BACKUP_DIR}/${TIMESTAMP}.tar.gz"
