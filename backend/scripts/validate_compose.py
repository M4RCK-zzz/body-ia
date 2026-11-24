"""Valida la composición de despliegue sin necesidad de Docker (Fase 9).

`docker compose config` no está disponible en todos los entornos (CI sin Docker,
sandbox, máquinas de desarrollo), pero los errores que más duelen —una variable de
entorno sin interpolar, un servicio sin `restart`, la base publicada al mundo, un
`depends_on` que no espera a las migraciones— sí se pueden detectar de forma
estática.

Este script:

1. Carga `docker-compose.yml` + `docker-compose.prod.yml` y los fusiona como hace
   Compose (el overlay gana; `ports: []` vacía la lista).
2. Interpola `${VAR}`, `${VAR:-default}` y exige `${VAR:?mensaje}` con el `.env`
   indicado.
3. Comprueba invariantes de producción que no deben relajarse.

Uso:
    python backend/scripts/validate_compose.py [--env .env.prod] [--quiet]

Devuelve 0 si todo cuadra y 1 con la lista de problemas.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - dependencia de desarrollo
    print("Falta PyYAML: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2) from None

ROOT = Path(__file__).resolve().parents[2]
BASE_FILE = ROOT / "docker-compose.yml"
PROD_FILE = ROOT / "docker-compose.prod.yml"

VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?:(:-|:\?)([^}]*))?\}")

ALLOWED_RESTART = {"no", "always", "unless-stopped", "on-failure"}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def interpolate(value: Any, env: dict[str, str], errors: list[str], where: str) -> Any:
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name, operator, argument = match.group(1), match.group(2), match.group(3) or ""
            if name in env and env[name] != "":
                return env[name]
            if operator == ":-":
                return argument
            if operator == ":" + "?":
                errors.append(f"{where}: variable obligatoria sin definir: {name} ({argument})")
                return ""
            errors.append(f"{where}: variable sin definir y sin valor por defecto: {name}")
            return ""

        return VAR_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [interpolate(item, env, errors, where) for item in value]
    if isinstance(value, dict):
        return {
            key: interpolate(item, env, errors, f"{where}.{key}")
            for key, item in value.items()
        }
    return value


def merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge superficial por servicio (como el overlay de Compose)."""
    result = dict(base)
    result["services"] = {name: dict(svc) for name, svc in (base.get("services") or {}).items()}
    for name, svc in (overlay.get("services") or {}).items():
        if name in result["services"]:
            result["services"][name].update(svc)
        else:
            result["services"][name] = dict(svc)
    for key in ("volumes", "networks", "secrets", "configs"):
        if key in overlay:
            merged = dict(result.get(key) or {})
            merged.update(overlay[key] or {})
            result[key] = merged
    return result


def check(composed: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    services: dict[str, dict[str, Any]] = composed.get("services") or {}

    expected = {
        "db",
        "migrate",
        "backend",
        "worker-pose",
        "worker-report",
        "worker-simulation",
        "frontend",
    }
    missing = expected - set(services)
    if missing:
        problems.append(f"faltan servicios de producción: {sorted(missing)}")

    # Servicios one-shot: terminan solos, no tienen política de reinicio.
    one_shot = {"migrate", "retention", "backup", "restore"}

    for name, svc in services.items():
        if "image" not in svc and "build" not in svc:
            problems.append(f"{name}: sin imagen ni build")
        restart = svc.get("restart")
        if name not in one_shot and restart not in ALLOWED_RESTART:
            problems.append(f"{name}: restart inválido o ausente ({restart!r})")
        if restart == "always" and name != "migrate":
            problems.append(
                f"{name}: 'restart: always' impide paradas ordenadas; usa unless-stopped"
            )
        for volume in svc.get("volumes") or []:
            if isinstance(volume, str) and volume.startswith("/") and ":" not in volume:
                problems.append(f"{name}: bind mount sin destino claro: {volume}")
        if "build" in svc and not Path(ROOT / svc["build"].get("dockerfile", "")).exists():
            problems.append(f"{name}: Dockerfile inexistente ({svc['build'].get('dockerfile')})")

    # La base no se publica en producción.
    db_ports = services.get("db", {}).get("ports")
    if db_ports:
        problems.append(f"db publica puertos en producción: {db_ports}")

    # La API espera a que las migraciones terminen bien.
    backend_deps = (services.get("backend", {}) or {}).get("depends_on") or {}
    migrate_condition = (backend_deps.get("migrate") or {}).get("condition")
    if migrate_condition != "service_completed_successfully":
        problems.append("backend no espera a que 'migrate' termine correctamente")

    # El job de migraciones es one-shot.
    migrate = services.get("migrate", {})
    if migrate.get("restart") not in {None, "no"}:
        problems.append("migrate no es one-shot (restart debe ser 'no')")
    if "upgrade" not in " ".join(str(part) for part in migrate.get("command") or []):
        problems.append("migrate no ejecuta 'alembic upgrade head'")
    api_command = (services.get("backend", {}) or {}).get("command") or []
    if "alembic" in " ".join(str(part) for part in api_command):
        problems.append("la API ejecuta alembic en su CMD (prohibido: usar el job migrate)")

    # Retención: `entrypoint` fija el módulo y `command` solo los argumentos, para
    # que `run --rm retention --apply` (documentado) añada el flag en vez de
    # sustituir el comando entero.
    retention = services.get("retention", {}) or {}
    retention_entry = " ".join(str(part) for part in retention.get("entrypoint") or [])
    retention_cmd = " ".join(str(part) for part in retention.get("command") or [])
    if "app.workers.retention_worker" not in retention_entry:
        problems.append("retention: el entrypoint debe fijar app.workers.retention_worker")
    if "--once" not in retention_cmd:
        problems.append("retention: command debe ser '--once' (los flags van detrás)")
    if "module" in retention_cmd or "python" in retention_cmd:
        problems.append(
            "retention: el módulo va en entrypoint; 'run --rm retention --apply' lo rompería"
        )

    # Backup/restore: necesitan el cliente de PostgreSQL (pg_dump/pg_restore/psql),
    # que la imagen de la API no trae. Deben construirse desde docker/ops.Dockerfile.
    for name in ("backup", "restore"):
        svc = services.get(name, {}) or {}
        dockerfile = (svc.get("build") or {}).get("dockerfile", "")
        if "ops.Dockerfile" not in str(dockerfile):
            problems.append(f"{name}: debe usar docker/ops.Dockerfile (cliente de PostgreSQL)")
        env = svc.get("environment") or {}
        if isinstance(env, dict) and not str(env.get("PGPASSWORD", "")).strip():
            problems.append(f"{name}: sin PGPASSWORD (pg_dump/psql no podrían autenticarse)")

    # La API debe estar en producción y con docs cerradas.
    backend_env = (services.get("backend", {}) or {}).get("environment") or {}
    if isinstance(backend_env, dict):
        if backend_env.get("ENVIRONMENT") != "production":
            problems.append("backend: ENVIRONMENT distinto de 'production'")
        if str(backend_env.get("ENABLE_API_DOCS", "")).lower() != "false":
            problems.append("backend: ENABLE_API_DOCS debe ser 'false' en producción")
        if str(backend_env.get("DEBUG", "false")).lower() == "true":
            problems.append("backend: DEBUG activo en producción")
        cors = str(backend_env.get("CORS_ORIGINS", ""))
        if "*" in cors or not cors.startswith("https://"):
            problems.append(f"backend: CORS_ORIGINS insegura en producción ({cors!r})")

    # Healthchecks reales en API y frontend.
    if "healthcheck" not in (services.get("backend", {}) or {}):
        problems.append("backend sin healthcheck")
    if "healthcheck" not in (services.get("frontend", {}) or {}):
        problems.append("frontend sin healthcheck")
    for name in ("worker-pose", "worker-report", "worker-simulation"):
        if "healthcheck" not in (services.get(name, {}) or {}):
            problems.append(f"{name} sin healthcheck")

    # El frontend publica 80/443 y monta certificados.
    frontend = services.get("frontend", {}) or {}
    ports = " ".join(str(port) for port in frontend.get("ports") or [])
    for port in ("443", "80"):
        if port not in ports:
            problems.append(f"frontend no publica el puerto {port}")
    if not any("certs" in str(volume) for volume in frontend.get("volumes") or []):
        problems.append("frontend no monta el volumen de certificados")

    return problems


def check_files() -> list[str]:
    """Comprobaciones sobre los ficheros de configuración del borde."""
    problems: list[str] = []
    raw = (ROOT / "docker/nginx/security-headers.conf").read_text(encoding="utf-8")
    # Solo las directivas reales: los comentarios explican por qué se permite
    # `wasm-unsafe-eval` y mencionan el término prohibido.
    csp_lines = [
        line for line in raw.splitlines() if line.strip().startswith("add_header")
    ]
    csp = "\n".join(csp_lines)
    for needle in ("wasm-unsafe-eval", "worker-src 'self' blob:", "img-src 'self' blob: data:"):
        if needle not in csp:
            problems.append(f"CSP de Nginx sin {needle!r} (rompería el visor 3D)")
    if "unsafe-eval" in csp.replace("wasm-unsafe-eval", ""):
        problems.append("CSP de Nginx contiene 'unsafe-eval' de JavaScript")
    if "Strict-Transport-Security" not in csp:
        problems.append("CSP de Nginx sin HSTS")

    template_path = ROOT / "docker/nginx/templates/bodyvision.conf.template"
    template = template_path.read_text(encoding="utf-8")
    if "${DOMAIN}" not in template:
        problems.append("la plantilla de Nginx no parametriza ${DOMAIN}")
    if "listen 443 ssl" not in template:
        problems.append("la plantilla de Nginx no sirve HTTPS")

    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for entry in (".env", "backend/storage", "node_modules"):
        if entry not in dockerignore:
            problems.append(f".dockerignore no excluye {entry}")

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    if "!.env.prod.example" not in gitignore:
        problems.append(".gitignore no permite versionar .env.prod.example")
    if not (ROOT / ".env.prod.example").exists():
        problems.append("falta .env.prod.example")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida la composición de producción")
    parser.add_argument("--env", default=".env.prod", help="fichero de variables a usar")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    env_path = Path(args.env)
    env = load_env(env_path if env_path.is_absolute() else Path.cwd() / env_path)
    errors: list[str] = []
    base = yaml.safe_load(BASE_FILE.read_text(encoding="utf-8")) or {}
    overlay = yaml.safe_load(PROD_FILE.read_text(encoding="utf-8")) or {}
    composed = merge(base, overlay)

    interpolated = interpolate(composed, env, errors, "compose")
    problems = errors + check(interpolated) + check_files()

    if problems:
        print(f"✗ {len(problems)} problema(s) en la composición de producción:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    services = sorted((interpolated.get("services") or {}).keys())
    if not args.quiet:
        print("✓ composición válida")
        print(f"  servicios: {', '.join(services)}")
        print(f"  variables desde: {args.env}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
