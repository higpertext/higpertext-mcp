"""Config de los backends dinámicos (Redis + profile server) por variable de entorno.

Mismo patrón que `discovery.resolve_project_root()`: override explícito por env,
con un default razonable para el caso común (todo corriendo en localhost, vía el
docker-compose de laboratorio de higpertext-server-profile).
"""

from __future__ import annotations

import os


def redis_url() -> str:
    return os.environ.get("HIGPERTEXT_REDIS_URL", "redis://localhost:6379/0")


def profile_server_addr() -> str:
    return os.environ.get("HIGPERTEXT_PROFILE_SERVER_ADDR", "localhost:50051")


def oidc_token_url() -> str:
    return os.environ.get(
        "HIGPERTEXT_OIDC_TOKEN_URL",
        "http://localhost:8081/realms/higpertext/protocol/openid-connect/token",
    )


def agent_client_id() -> str:
    return os.environ.get("HIGPERTEXT_AGENT_CLIENT_ID", "htx-agent")


def agent_client_secret() -> str:
    """Secreto de la cuenta de servicio del agente, por env o por archivo
    (`HIGPERTEXT_AGENT_CLIENT_SECRET_FILE`, p. ej. un docker secret). Vacío si
    no está configurado. Nunca se loguea ni se devuelve en mensajes de error."""
    direct = os.environ.get("HIGPERTEXT_AGENT_CLIENT_SECRET", "").strip()
    if direct:
        return direct
    path = os.environ.get("HIGPERTEXT_AGENT_CLIENT_SECRET_FILE", "").strip()
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def oidc_host_header() -> str:
    """Host con el que Keycloak debe emitir el token (su `iss`). Útil cuando el MCP
    llega por un nombre interno (keycloak:8080) pero la API exige el issuer público
    (localhost:8081). Vacío = no se fuerza la cabecera."""
    return os.environ.get("HIGPERTEXT_OIDC_HOST_HEADER", "").strip()


def profile_source() -> str:
    """De dónde sale el perfil activo de un repositorio (RFC-0020).

    "server" (por defecto): el RepositoryConfig del servidor, con
    .higpertext/config/environment.json como respaldo si el servidor no responde
    o el repositorio aún no tiene perfil allí. "local": solo el archivo, como antes
    de RFC-0020.
    """
    return "local" if os.environ.get("HIGPERTEXT_PROFILE_SOURCE", "").strip().lower() == "local" else "server"
