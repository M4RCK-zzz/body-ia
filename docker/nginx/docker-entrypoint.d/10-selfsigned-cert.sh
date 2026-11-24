#!/bin/sh
# Certificado autofirmado de conveniencia (Fase 9).
#
# SOLO para staging local o para arrancar el stack antes de tener el certificado
# real. Si ya existen /etc/nginx/certs/fullchain.pem y privkey.pem (Let's Encrypt
# o corporativo), no se toca nada.
#
#   ALLOW_SELFSIGNED=true   -> genera un certificado de 30 días si faltan ficheros
set -eu

CERT_DIR=/etc/nginx/certs
DOMAIN="${DOMAIN:-bodyvision.example.com}"

if [ -f "$CERT_DIR/fullchain.pem" ] && [ -f "$CERT_DIR/privkey.pem" ]; then
  echo "[tls] certificado presente en $CERT_DIR; no se genera nada"
  exit 0
fi

if [ "${ALLOW_SELFSIGNED:-false}" != "true" ]; then
  echo "[tls] ERROR: faltan fullchain.pem/privkey.pem en $CERT_DIR." >&2
  echo "[tls] Monta el certificado real o arranca con ALLOW_SELFSIGNED=true (solo pruebas)." >&2
  exit 1
fi

echo "[tls] generando certificado AUTOFIRMADO para $DOMAIN (solo pruebas)"
mkdir -p "$CERT_DIR"
openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
  -keyout "$CERT_DIR/privkey.pem" \
  -out "$CERT_DIR/fullchain.pem" \
  -subj "/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1" 2>/dev/null
cp "$CERT_DIR/fullchain.pem" "$CERT_DIR/chain.pem"
chmod 600 "$CERT_DIR/privkey.pem"
echo "[tls] listo (el navegador avisará de que no es de confianza: es lo esperado)"
