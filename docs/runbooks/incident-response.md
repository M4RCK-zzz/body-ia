# Runbook · Respuesta a incidentes

**Objetivo:** contener, evaluar, recuperar y aprender. Sin dramatismo y sin atajos.

## Clasificación

| Severidad | Ejemplo | Respuesta |
|---|---|---|
| **S1** | Datos personales expuestos; producción caída; corrupción de datos | Inmediata, 24/7 |
| **S2** | Una función crítica no responde; worker caído; errores 500 puntuales | Antes de 1 h |
| **S3** | Degradación menor; un endpoint lento | Siguiente día laborable |

## Flujo

1. **Detectar** — alerta o reporte. Anotar hora exacta (UTC) y quién lo detectó.
2. **Contener** — ¿hay fuga? Revocar acceso (`/api/profiles/{id}/access`), desactivar usuario
   (`/api/admin/users/{id}/deactivate`) o rotar `JWT_SECRET` (invalida todas las sesiones).
3. **Evaluar** — alcance: qué datos, qué usuarios, qué ventana temporal. La auditoría
   (`audit_events`, con `request_id`) es la fuente de verdad.
4. **Recuperar** — restaurar servicio (`rollback.md`, `backup-restore.md`).
5. **Comunicar** — si hay datos personales afectados, la notificación es obligatoria y tiene
   plazos legales; no se improvisa.
6. **Aprender** — post-mortem en 5 días, sin culpables, con acciones con dueño y fecha.

## Consultas de diagnóstico

```sql
-- Eventos de la última hora, por tipo
SELECT action, count(*) FROM audit_events
WHERE occurred_at > now() - interval '1 hour'
GROUP BY action ORDER BY 2 DESC;

-- Denegaciones de acceso (posible intento de IDOR o permisos mal puestos)
SELECT actor_user_id, profile_id, detail, occurred_at FROM audit_events
WHERE action = 'access.denied' AND occurred_at > now() - interval '24 hours'
ORDER BY occurred_at DESC;

-- Rastro de una petición concreta
SELECT action, actor_user_id, resource_id, occurred_at FROM audit_events
WHERE detail->>'request_id' = '<id>';
```

## Qué NO hacer

- No borrar filas de `audit_events` (el trigger tampoco lo permitirá).
- No "arreglar" datos a mano en producción sin backup y sin registrar el cambio.
- No rotar `JWT_SECRET` sin avisar: cierra la sesión de todos los usuarios.
