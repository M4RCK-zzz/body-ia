# Runbook · Despliegue

**Objetivo:** llevar una versión nueva a producción sin pérdida de datos ni ventana de
inconsistencia. **Tiempo esperado:** 15–30 min. **Riesgo:** medio (migraciones).

## Antes de empezar

- [ ] CI en verde en la rama que se va a desplegar (ruff, pytest, lint, build, compose).
- [ ] Release anotada y `APP_VERSION` decidida.
- [ ] **Backup reciente y verificado** (`backup.ps1` + restauración de ensayo). Sin esto, no
      se despliega.
- [ ] Ventana de mantenimiento comunicada si la migración toca tablas grandes.
- [ ] `.env.prod` revisado: `DOMAIN`, `CORS_ORIGINS`, `JWT_SECRET`, `ALLOW_REGISTRATION=false`.

## Pasos

```bash
# 1. Código
git fetch --tags && git checkout <tag>
git log --oneline -1   # confirmar versión

# 2. Construir imágenes (sin levantar nada todavía)
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 3. Validar la composición antes de tocar producción
python backend/scripts/validate_compose.py --env .env.prod

# 4. Migraciones (job one-shot; si falla, SE ABORTA y no se levanta la API)
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate

# 5. Levantar/recrear servicios
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 6. Verificar
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -fsS https://$DOMAIN/api/health/live
curl -fsS https://$DOMAIN/api/health/ready
curl -fsS -H "Authorization: Bearer $ADMIN_TOKEN" https://$DOMAIN/api/health/workers
curl -sI https://$DOMAIN/ | grep -Ei "content-security|strict-transport|x-frame"
```

## Verificación funcional (5 min)

1. Login con una cuenta real → dashboard carga.
2. Un expediente existente abre y muestra sus mediciones (sin datos perdidos).
3. Analítica responde y el PDF de un reporte se descarga.
4. El visor 3D carga un modelo **sin errores de CSP en la consola**.
   El panel **Administración → Workers** (solo `admin`) muestra los latidos; la API responde
   `401`/`403` a `/api/health/workers` sin sesión de administrador.
5. El simulador muestra el comparador con el aviso "ESCENARIO HIPOTÉTICO".

## Si algo falla

→ `docs/runbooks/rollback.md`. **Nunca** se deja producción a medias: o queda entera en la
versión nueva o entera en la anterior.

## Registro

| Campo | Valor |
|---|---|
| Versión desplegada | |
| Revisión Alembic | |
| Fecha / hora (UTC) | |
| Ejecutado por | |
| Incidencias | |
