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
