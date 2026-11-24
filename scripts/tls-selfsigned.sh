#!/usr/bin/env bash
# Genera un certificado TLS AUTOFIRMADO para probar HTTPS en local/staging (Fase 9).
#
#   ./scripts/tls-selfsigned.sh                       # CN=localhost, 30 días
#   ./scripts/tls-selfsigned.sh bodyvision.example.com 60
#   DOMAIN=mi.dominio ./scripts/tls-selfsigned.sh
#
# Escribe fullchain.pem / privkey.pem / chain.pem en $OUT_DIR y los deja con
# permisos 600. El navegador avisará de que el certificado no es de confianza:
# es lo esperado y NO sirve para producción.
#
# Para producción: monta los ficheros de Let's Encrypt
# (/etc/letsencrypt/live/$DOMAIN/) o tu certificado corporativo y arranca sin
# ALLOW_SELFSIGNED.
set -euo pipefail

DOMAIN="${1:-${DOMAIN:-localhost}}"
DAYS="${2:-30}"
OUT_DIR="${OUT_DIR:-docker/nginx/certs}"

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: falta 'openssl' en el PATH." >&2
  exit 1
fi

case "$DAYS" in
  ''|*[!0-9]*)
    echo "ERROR: los días deben ser un número entero (recibido: '$DAYS')." >&2
    exit 1
    ;;
esac

if [ "$DAYS" -gt 825 ]; then
  echo "ERROR: los navegadores rechazan certificados de más de 825 días." >&2
  exit 1
fi

if [ -f "$OUT_DIR/fullchain.pem" ] && [ "${FORCE:-false}" != "true" ]; then
  echo "Ya existe $OUT_DIR/fullchain.pem."
  echo "Si quieres regenerarlo, bórralo o ejecuta con FORCE=true."
  exit 0
fi

mkdir -p "$OUT_DIR"

openssl req -x509 -nodes -newkey rsa:2048 -days "$DAYS" \
  -keyout "$OUT_DIR/privkey.pem" \
  -out "$OUT_DIR/fullchain.pem" \
  -subj "/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1" 2>/dev/null

cp "$OUT_DIR/fullchain.pem" "$OUT_DIR/chain.pem"
chmod 600 "$OUT_DIR/privkey.pem"

echo "Certificado autofirmado generado en $OUT_DIR:"
echo "  subject : $(openssl x509 -in "$OUT_DIR/fullchain.pem" -noout -subject)"
echo "  caduca  : $(openssl x509 -in "$OUT_DIR/fullchain.pem" -noout -enddate)"
echo
echo "Recuerda: solo para pruebas. En producción, certificado real."
echo "Montaje en docker-compose.prod.yml: ./docker/nginx/certs:/etc/nginx/certs:ro"
