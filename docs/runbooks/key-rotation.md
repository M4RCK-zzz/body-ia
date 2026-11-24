# Runbook · Rotación de secretos

## `JWT_SECRET` (rotación periódica o compromiso)

**Efecto:** todas las sesiones activas se invalidan; los usuarios deben volver a entrar.
Planificarlo con comunicación previa.

```bash
# 1. Generar uno nuevo (≥32 caracteres, nunca el de ejemplo)
python -c "import secrets; print(secrets.token_urlsafe(48))"

# 2. Actualizar .env.prod (nunca en el repo) y recrear SOLO los servicios que lo usan
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate \
  backend worker-report worker-simulation

# 3. Verificar
curl -fsS https://$DOMAIN/api/health/ready
```

Los workers de reportes y simulación no validan tokens de usuario, pero se recrean para no
dejar configuraciones mezcladas.

## `POSTGRES_PASSWORD`

```bash
# 1. Cambiar en PostgreSQL
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db \
  psql -U bodyvision -c "ALTER USER bodyvision WITH PASSWORD '<nueva>';"

# 2. Actualizar .env.prod y recrear API y workers
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate \
  backend worker-pose worker-report worker-simulation

# 3. Verificar readiness y un login real
```

## Certificado TLS

| Origen | Renovación |
|---|---|
| Let's Encrypt (certbot) | Automática cada 60–90 días; `nginx -s reload` tras renovar |
| Certificado corporativo | Calendario con aviso 30 días antes |
| Autofirmado (`ALLOW_SELFSIGNED=true`) | Solo pruebas; **no** usar en producción |

Los certificados se montan en `docker/nginx/certs/` (`fullchain.pem` + `privkey.pem` +
`chain.pem`): no hay variables `SSL_CERT`/`SSL_KEY` y las claves nunca entran al repo.

```bash
# Comprobar caducidad
openssl s_client -connect $DOMAIN:443 -servername $DOMAIN </dev/null 2>/dev/null \
  | openssl x509 -noout -dates
```

## Registro de rotaciones

| Secreto | Fecha | Motivo | Ejecutado por |
|---|---|---|---|
| | | | |
