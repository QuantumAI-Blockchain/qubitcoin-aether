#!/usr/bin/env bash
# ============================================================================
# Certbot SSL Certificate Management — Qubitcoin
# Usage:
#   ./certbot-renew.sh init     — First-time certificate issuance
#   ./certbot-renew.sh renew    — Renew existing certificates
#   ./certbot-renew.sh status   — Check certificate status
# ============================================================================

set -euo pipefail

DOMAIN="api.qbc.network"
EMAIL="admin@qbc.network"
WEBROOT="/var/www/certbot"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"

case "${1:-renew}" in
  init)
    echo "==> Issuing initial certificate for ${DOMAIN}..."
    mkdir -p "${WEBROOT}"
    certbot certonly \
      --webroot \
      --webroot-path="${WEBROOT}" \
      --domain "${DOMAIN}" \
      --domain "rpc.qbc.network" \
      --email "${EMAIL}" \
      --agree-tos \
      --no-eff-email \
      --non-interactive \
      --force-renewal
    echo "==> Certificate issued. Reloading nginx..."
    nginx -s reload
    ;;

  renew)
    echo "==> Renewing certificates..."
    certbot renew \
      --quiet \
      --deploy-hook "nginx -s reload"
    echo "==> Renewal check complete."
    ;;

  status)
    echo "==> Certificate status:"
    if [ -d "${CERT_DIR}" ]; then
      openssl x509 -in "${CERT_DIR}/fullchain.pem" -noout -dates -subject
    else
      echo "   No certificate found at ${CERT_DIR}"
      echo "   Run: $0 init"
    fi
    ;;

  *)
    echo "Usage: $0 {init|renew|status}"
    exit 1
    ;;
esac
