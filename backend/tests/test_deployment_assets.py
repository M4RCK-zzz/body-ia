"""Activos de despliegue (Fase 9): invariantes de la composición y del borde.

Se ejecutan sin Docker para que el gate funcione en CI y en cualquier máquina:
el validador reproduce el merge y la interpolación de `docker compose config`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "validate_compose.py"


@pytest.fixture(scope="module")
def env_file(tmp_path_factory) -> Path:
    """Un `.env.prod` de pruebas con secretos falsos pero válidos en forma."""
    env = tmp_path_factory.mktemp("env") / ".env.prod"
    env.write_text(
        "\n".join(
            [
                "APP_VERSION=0.1.0",
                "DOMAIN=bodyvision.example.com",
                "ALLOW_SELFSIGNED=true",
                "POSTGRES_DB=bodyvision",
                "POSTGRES_USER=bodyvision",
                "POSTGRES_PASSWORD=test-password-0123456789",
                "ENVIRONMENT=production",
                "DEBUG=false",
                "LOG_JSON=true",
                "CORS_ORIGINS=https://bodyvision.example.com",
                "TRUSTED_PROXIES=true",
                "ENABLE_API_DOCS=false",
                "JWT_SECRET=" + "x" * 48,
                "UPLOAD_DIR=/app/storage",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return env


def _run(env_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--env", str(env_file)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )


def test_production_composition_is_valid(env_file: Path) -> None:
    result = _run(env_file)
    assert result.returncode == 0, result.stderr


def test_missing_required_variable_fails(env_file: Path) -> None:
    """Sin `DOMAIN` no hay `server_name` ni CORS: el validador lo detecta."""
    truncated = env_file.parent / "sin-domain.env"
    truncated.write_text(
        "\n".join(
            line
            for line in env_file.read_text(encoding="utf-8").splitlines()
            if not line.startswith(("DOMAIN=", "CORS_ORIGINS="))
        ),
        encoding="utf-8",
    )
    result = _run(truncated)
    assert result.returncode == 1
    assert "DOMAIN" in result.stderr


def test_nginx_csp_allows_draco_wasm() -> None:
    csp = (ROOT / "docker/nginx/security-headers.conf").read_text(encoding="utf-8")
    directives = [line for line in csp.splitlines() if line.strip().startswith("add_header")]
    joined = "\n".join(directives)
    assert "'wasm-unsafe-eval'" in joined
    assert "worker-src 'self' blob:" in joined
    assert "img-src 'self' blob: data:" in joined
    assert "unsafe-eval" not in joined.replace("wasm-unsafe-eval", "")


def test_dockerfiles_do_not_run_as_root() -> None:
    for dockerfile in ("backend.Dockerfile", "worker-pose.Dockerfile"):
        content = (ROOT / "docker" / dockerfile).read_text(encoding="utf-8")
        assert "USER app" in content, dockerfile
        assert "--no-cache-dir" in content or "PIP_NO_CACHE_DIR=1" in content, dockerfile


def test_dockerignore_excludes_secrets_and_user_data() -> None:
    content = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for entry in (".env", "backend/storage", "node_modules", "**/__pycache__"):
        assert entry in content


def test_env_prod_template_has_no_real_secrets() -> None:
    template = (ROOT / ".env.prod.example").read_text(encoding="utf-8")
    assert "CAMBIA-ESTE-SECRETO" in template
    assert "ENABLE_API_DOCS=false" in template
    assert "RETENTION_DRY_RUN=true" in template
    assert "CORS_ORIGINS=https://" in template


def test_tls_scripts_exist_for_both_shells() -> None:
    """El comentario de `nginx.conf` promete: autofirmado para probar HTTPS local."""
    sh = ROOT / "scripts" / "tls-selfsigned.sh"
    ps1 = ROOT / "scripts" / "tls-selfsigned.ps1"
    assert sh.is_file() and ps1.is_file()
    assert sh.stat().st_mode & 0o111, "tls-selfsigned.sh debe ser ejecutable"

    sh_text = sh.read_text(encoding="utf-8")
    assert "openssl req -x509" in sh_text
    assert "chmod 600" in sh_text
    assert "825" in sh_text, "debe rechazar vigencias que los navegadores no aceptan"

    ps1_text = ps1.read_text(encoding="utf-8")
    assert "openssl req -x509" in ps1_text
    assert "ValidateRange(1, 825)" in ps1_text
    assert "SetAccessRuleProtection" in ps1_text, "la clave privada necesita ACL restringida"


def test_certificates_are_never_committed() -> None:
    """`docker/nginx/certs` es un bind mount: las claves privadas no entran al repo."""
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "./docker/nginx/certs:/etc/nginx/certs" in compose

    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "docker/nginx/certs/*" in ignore
    assert "!docker/nginx/certs/.gitkeep" in ignore

    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "docker/nginx/certs" in dockerignore, "la clave privada no entra en el contexto de build"
