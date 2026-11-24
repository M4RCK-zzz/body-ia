# Roadmap — proyecto completo (fases 1–9 cerradas)

## Estado del proyecto

Las nueve fases están cerradas. El producto está desplegado como plantilla
reproducible (`docker-compose.prod.yml` + `docker/`), con CI en GitHub Actions,
observabilidad por `request_id`, backups verificables y retención efectiva.

| Documento | Contenido |
|---|---|
| `docs/ARQUITECTURA.md` | **ADR-002 a ADR-012** (no existe ADR-001: la numeración arranca en el 002) |
| `docs/QA_CHECKLIST.md` | Checklist de cierre con evidencia por ítem |
| `docs/SEGURIDAD_Y_PRIVACIDAD.md` | Modelo de amenazas, mapa de datos y riesgos residuales |
| `docs/runbooks/` | Despliegue, rollback, backup/restore, incidentes, rotación de claves, worker caído, disco lleno y BD caída |

## Resumen de fases

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Base de datos, tipos de dato y catálogo de métricas | Cerrada |
| 2 | Expedientes y mediciones inmutables | Cerrada |
| 3 | Identidad, RBAC y auditoría append-only | Cerrada |
| 4 | Captura segura y storage privado | Cerrada |
| 5 | Análisis de pose (MediaPipe, worker asíncrono, revisión) | Cerrada |
| 6 | Visor 3D (activos GLB/GLTF, R3F, capas) | Cerrada |
| 7 | Analítica descriptiva y reportes CSV/PDF (worker, auditoría, dashboard real) | Cerrada |
| 8 | Simulación hipotética (escenarios aislados) | Cerrada |
| 9 | Producción: despliegue endurecido, observabilidad, backups, retención, QA y ADR-010 | Cerrada |
| — | Ampliaciones posteriores: panel de Administración (ADR-011) y ajustes del visor/listas (ADR-012) | Cerrada |
