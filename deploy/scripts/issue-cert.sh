#!/usr/bin/env bash
# Issue a Let's Encrypt cert via certbot in standalone mode.
#
# Usage: EMAIL=you@example.com DOMAIN=docconv.example.com ./deploy/scripts/issue-cert.sh
set -euo pipefail

EMAIL="${EMAIL:?EMAIL is required}"
DOMAIN="${DOMAIN:?DOMAIN is required}"
WEBROOT="/var/www/certbot"
CERT_DIR="/etc/nginx/certs"

mkdir -p "${WEBROOT}" "${CERT_DIR}"

docker run --rm \
  -v "${CERT_DIR}:/etc/letsencrypt" \
  -v "${WEBROOT}:/var/www/certbot" \
  certbot/certbot certonly \
    --webroot --webroot-path=/var/www/certbot \
    --email "${EMAIL}" --agree-tos --no-eff-email \
    -d "${DOMAIN}"

# Symlink the live certs into the nginx path expected by the config.
ln -sf "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "${CERT_DIR}/fullchain.pem"
ln -sf "/etc/letsencrypt/live/${DOMAIN}/privkey.pem"   "${CERT_DIR}/privkey.pem"

# Auto-renew cron entry
( crontab -l 2>/dev/null | grep -v 'certbot renew' ;
  echo "0 3 * * * docker run --rm -v ${CERT_DIR}:/etc/letsencrypt -v ${WEBROOT}:/var/www/certbot certbot/certbot renew --webroot --webroot-path=/var/www/certbot --quiet && docker exec docformatconverter-nginx-1 nginx -s reload" ) | crontab -

echo "[cert] issued and renewal cron installed for ${DOMAIN}"
