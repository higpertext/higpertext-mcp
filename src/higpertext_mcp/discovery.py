"""Resuelve raíz de proyecto, perfil activo y capabilities permitidas.

Usa resolución basada en cwd — el mismo patrón que higpertext-cli usa para sus
hooks (`hook_utils.get_project_root`) — NO `higpertext.kernel.config_paths.PROJECT_ROOT`,
que resuelve la raíz del *motor instalado*, no la del proyecto destino. Ver
docs/architecture.md para el porqué de esta distinción.

El catálogo de capabilities permitidas (`allowed_capabilities`) ya NO se resuelve
contra JSON estático del motor instalado: se consulta en runtime al profile server
(`profile_client`) — perfil + catálogo son ahora dinámicos, administrables sin
redeploy de higpertext-mcp. `active_profile()` sigue local (lee
`.higpertext/config/environment.json`): decidir *qué* perfil está activo en este
proyecto no es responsabilidad del profile server, solo *qué puede hacer* ese perfil.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from higpertext_mcp import profile_client
from higpertext_mcp.gen.profile.v1 import profile_pb2

_WORKSPACE_DIR = ".higpertext"


def resolve_project_root() -> Path:
    """Raíz del proyecto destino: override explícito o cwd del proceso servidor."""
    override = os.environ.get("HIGPERTEXT_PROJECT_ROOT")
    if override:
        return Path(override).resolve()
    return Path.cwd()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def active_profile(root: Path) -> str | None:
    env = _read_json(root / _WORKSPACE_DIR / "config" / "environment.json")
    return env.get("active_profile") or None


async def allowed_capabilities(root: Path) -> list[profile_pb2.Capability]:
    """Intersección entre el catálogo del profile server y lo que el perfil activo permite.

    Devuelve los `Capability` completos (metadata + parámetros + contrato),
    no solo ids — son la fuente de verdad para armar cada ToolSpec (ver
    `schema.tool_spec_from_capability`).

    Fail-closed: sin perfil activo, o si el profile server no responde, no se
    expone nada (ver `profile_client.list_allowed_capabilities`).
    """
    return await profile_client.list_allowed_capabilities(active_profile(root))
