# Seguridad y privacidad — BODYVISION AI

> Documento de referencia del modelo de seguridad de la aplicación, actualizado en la
> **Fase 9**. Describe qué datos se guardan, dónde, quién puede verlos y qué controles los
> protegen, con la referencia al código y al test que lo demuestran. Cuando algo **no** está
> cubierto, se dice explícitamente: un riesgo declarado es un riesgo gestionado; uno oculto,
> no.

**Alcance del sistema.** BODYVISION AI registra mediciones corporales, capturas fotográficas,
estimaciones visuales de pose (MediaPipe) y escenarios hipotéticos. **No es un producto
sanitario**: no emite diagnósticos, no prescribe y no sustituye una valoración profesional.

---

## 1. Activos protegidos

| Activo | Dónde vive | Sensibilidad |
|---|---|---|
| Credenciales (email, hash argon2) | `users` (PostgreSQL) | Alta |
| Datos de expediente (código, estado) | `profiles` | Media |
| Mediciones corporales | `measurements` (inmutable, versionada) | **Alta** (dato de salud) |
| Imágenes de captura | storage privado (disco), metadatos en `media_assets` | **Alta** (imagen corporal) |
| Estimaciones de pose | `pose_analyses` (`data_kind=visual_estimate`) | Alta |
| Reportes CSV/PDF | binarios en storage, metadatos en `reports` | Alta |
| Escenarios hipotéticos | `simulations` + `simulation_baselines` (`data_kind=simulation`) | Media |
| Auditoría | `audit_events` (append-only) | Alta (integridad) |
| Secretos (`JWT_SECRET`, contraseña de BD) | variables/`secrets` fuera del repo | Crítica |

**Regla de oro heredada de la Fase 1:** todo dato lleva su `DataKind` (`observed`,
`visual_estimate`, `simulation`) y nunca se mezclan en una misma superficie sin etiqueta.

---

## 2. Modelo de amenazas (STRIDE abreviado)

| Amenaza | Escenario concreto | Control |
|---|---|---|
| **S**poofing | Robo de token; suplantación de sesión | JWT HS256 firmado, 30 min, `jti`; argon2id; bloqueo de cuenta tras 5 fallos |
| **T**ampering | Modificar una medición o un evento de auditoría | `measurements` inmutable (solo se corrige creando otra fila); triggers en `audit_events`, `simulations`, `worker_heartbeats` |
| **R**epudiation | "Yo no borré eso" | Auditoría append-only con actor, recurso, `detail` y `request_id` |
| **I**nformation disclosure | IDOR: pedir el expediente de otro cambiando el UUID | `AccessGuard` en cada recurso: **404** sin acceso (no revela existencia) |
| | Fuga entre usuarios en listados | Listados filtrados por acceso vigente (`revoked_at IS NULL`) |
| | Fuga por descarga de archivo | Descargas autenticadas, checksum revalidado, `no-store` |
| **D**enial of service | Fuerza bruta de login; abuso de workers | Rate limiting por IP/usuario + `limit_req` en Nginx + bloqueo de cuenta |
| **E**levation of privilege | `admin` leyendo expedientes ajenos | `admin` **no** tiene acceso implícito (404); RBAC + acceso por expediente |
| **XSS / clickjacking** | Inyección de script; iframe malicioso | CSP estricta, `X-Frame-Options: DENY`, `frame-ancestors 'none'` |
| **Fuga de secretos** | `.env` commiteado; secreto en la imagen | `.gitignore` + `.dockerignore` + plantilla sin secretos + guardas de arranque |

---

## 3. Mapa de datos y ciclo de vida

| Dato | Tabla / storage | Retención | Borrado |
|---|---|---|---|
| Usuario | `users` | Mientras exista la cuenta | Desactivación (`is_active=false`), sin borrado físico |
| Expediente | `profiles` | Mientras exista | Archivado lógico (`archived`), restaurable |
| Medición | `measurements` | **Indefinida** (trazabilidad) | **Nunca**; se corrige con una nueva versión |
| Imagen | `media_assets` + storage | `MEDIA_RETENTION_DAYS` (365) | Purga por retención: binario borrado, fila a `deleted` |
| Pose | `pose_analyses` | Indefinida | No se purga (es traza de una estimación) |
| Reporte | `reports` + storage | `REPORT_RETENTION_DAYS` (365) | Binario borrado; fila a `failed` con `retention_purged` |
| Simulación | `simulations` | `SIMULATION_RETENTION_DAYS` (365) | `result_json` limpiado; base conservada |
| Auditoría | `audit_events` | **Indefinida** | **Nunca** (append-only por trigger) |

**Dónde no están los datos:** el navegador solo guarda el token de sesión en
`sessionStorage` (se borra al cerrar la pestaña) y **nunca** toca PostgreSQL ni el storage
directamente: todas las operaciones pasan por la API con el token.

---

## 4. Controles implementados

### 4.1 Autenticación y sesión

| Control | Detalle | Código / test |
|---|---|---|
| Hash de contraseña | argon2id (`argon2-cffi`) | `app/core/passwords.py`, `tests/test_passwords.py` |
| Política de contraseña | ≥10 y ≤128 caracteres, letra + número | `app/domain/identity.py` |
| Token | JWT HS256, `iss`/`aud`/`exp`/`jti`, 30 min | `app/core/tokens.py`, `tests/test_tokens.py` |
| Bloqueo de cuenta | 5 intentos → 15 min; se audita `auth.account_locked` | `app/services/auth_service.py` |
| Mensaje de error genérico | No revela si el email existe | `_GENERIC_LOGIN_ERROR` |
| Registro | Desactivable por entorno (`ALLOW_REGISTRATION=false` en producción) | `Settings` |

### 4.2 Autorización

- **RBAC** (`user`, `admin`) + **acceso por expediente** (`owner`/`editor`/`viewer`).
- `admin` **no** obtiene acceso implícito: cualquier lectura de expediente ajeno da 404.
- Revocar acceso tiene efecto inmediato en la siguiente petición.
- Toda denegación se audita (`access.denied`) **solo si el expediente existe**: así no se
  puede usar la auditoría como oráculo de existencia.
- Cobertura: `tests/test_security_idor.py` (35 casos sobre 15 rutas).

### 4.3 Transporte y cabeceras (Fase 9)

```
Strict-Transport-Security: max-age=31536000; includeSubDomains   (solo fuera de local)
Content-Security-Policy: default-src 'self'; script-src 'self' 'wasm-unsafe-eval';
  worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:;
  font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
```

- `wasm-unsafe-eval` es **imprescindible** para el decodificador Draco del visor 3D
  (WebAssembly). No habilita `eval` de JavaScript: eso seguiría bloqueado y está verificado
  por test (`tests/test_security_headers.py`, `tests/test_deployment_assets.py`).
- `style-src 'unsafe-inline'` se mantiene por los estilos inline de React/R3F. **No** se
  relaja `script-src`.
- Se aplican en **dos capas**: middleware de FastAPI y Nginx.
- HSTS solo fuera de `local`, porque en local no hay TLS real.

### 4.4 CORS

- Lista explícita de orígenes; en producción se exige `https://` y se rechaza `*`
  **al arrancar**.
- Métodos y cabeceras enumerados (nunca `*`), `expose_headers` limitado.
- En producción el frontend y la API comparten origen (proxy de Nginx), así que CORS
  apenas interviene: es defensa en profundidad, no la única barrera.

### 4.5 Rate limiting (Fase 9)

| Endpoint | Límite | Clave |
|---|---|---|
| `POST /api/auth/login` | 5/min y 20/h | IP, y 20/h por email |
| `POST /api/auth/register` | 3/h | IP |
| Subidas, pose, reportes, simulaciones | 60/h | usuario |
| Descargas (`*/content`) | 120/h | usuario |
| Resto | 600/min | IP |

- `429` con `Retry-After`; event de log con la regla aplicada.
- `/api/health*` y `/api/docs` **nunca** se limitan.
- La clave se guarda **hasheada** (SHA-256 truncado): ni IPs ni emails en claro.

### 4.6 Protección de archivos

- Almacenamiento privado fuera de la raíz web, layout con shard, permisos `0600`,
  escritura atómica, clave UUID validada por patrón (nunca un path del usuario).
- Imágenes: se valida el contenido real (no el `Content-Type` declarado), límite de píxeles
  y de bytes, y **se elimina el EXIF** con transposición previa (Fase 4).
- Descargas: autenticadas, con revalidación de checksum y `Cache-Control: private, no-store`.

### 4.7 Auditoría

- `audit_events` es append-only: un trigger de BD rechaza `UPDATE` y `DELETE`.
- Cada evento guarda actor, acción, recurso, expediente, `detail` y (desde la Fase 9) el
  `request_id` de la petición, lo que permite cruzar un evento con su línea de log.

### 4.8 Secretos y despliegue

- `.env` y `.env.prod` fuera del repo; `.dockerignore` los excluye de cualquier imagen.
- Plantilla versionada (`.env.prod.example`) **sin secretos reales**.
- Guardas de arranque: en `production` la API **no arranca** con `DEBUG=true`, CORS `*` o
  `http://`, `ENABLE_API_DOCS=true`, o un `JWT_SECRET` débil o de ejemplo.
- Contenedores sin privilegios (`USER app`, uid 10001); la base no publica puertos.

---

## 5. Riesgos residuales aceptados

| Riesgo | Por qué se acepta | Mitigación |
|---|---|---|
| Token en `sessionStorage` | Evita CSRF por diseño y no requiere cambios de contrato; es accesible a XSS | CSP estricta sin `unsafe-inline` en script; `sessionStorage` muere al cerrar la pestaña |
| Rate limit **en memoria** | Sin Redis (la cola es PostgreSQL) | Nginx aplica `limit_req` en el borde; con N réplicas el efectivo es N× |
| Sin 2FA | Fuera del alcance del proyecto | Contraseña fuerte + bloqueo de cuenta + auditoría |
| Sin revocación individual de tokens | No hay lista de revocación | Rotación de `JWT_SECRET` (invalida todas las sesiones) y tokens de 30 min |
| Cifrado en reposo a nivel de aplicación | Se delega en el disco/volumen cifrado del proveedor | Documentado en el runbook de despliegue |
| Backups no cifrados por la app | Cifrado en destino (volumen/almacenamiento) | Ver D16 en ADR-010 |
| Sin WAF ni protección DDoS de capa 7 | Fuera de alcance | Reverse proxy + límites de Nginx |
| `mediapipe`/`cv2` requieren GL | Necesario para el worker de pose | Imagen separada solo para ese worker |

---

## 6. Derechos del usuario y del titular de los datos

| Derecho | Cómo se ejerce |
|---|---|
| **Acceso** | El expediente muestra todas las mediciones, pose, reportes y escenarios |
| **Rectificación** | Corrección de medición: se crea una nueva versión y la anterior queda histórica (nunca se sobrescribe) |
| **Supresión** | Archivado lógico del expediente; borrado efectivo de imágenes y binarios por retención; las mediciones y la auditoría se conservan por trazabilidad |
| **Retirada del consentimiento** | Revocación inmediata: bloquea nuevas escrituras en el expediente |
| **Portabilidad** | Reportes CSV/PDF de mediciones y de pose (separados por `DataKind`) |
| **Información** | Avisos no clínicos permanentes en todas las superficies |

**Consentimiento.** Se exige consentimiento vigente de `data_processing` antes de cualquier
escritura en un expediente; su aceptación y revocación se auditan.

---

## 7. Verificación

| Qué | Comando |
|---|---|
| Anti-IDOR | `pytest tests/test_security_idor.py -q` |
| Rate limiting | `pytest tests/test_rate_limit.py -q` |
| Cabeceras y CSP | `pytest tests/test_security_headers.py -q` |
| Guardas de producción | `pytest tests/test_config_environment.py -q` |
| Correlación de logs | `pytest tests/test_logging_correlation.py -q` |
| Retención sin daño | `pytest tests/test_retention_worker.py -q` |
| Activos de despliegue | `pytest tests/test_deployment_assets.py -q` |

El detalle operativo (qué hacer y en qué orden) está en `docs/QA_CHECKLIST.md` y en
`docs/runbooks/`.
