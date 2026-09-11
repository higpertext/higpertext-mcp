"""Resuelve raíz de proyecto, perfil activo y capabilities permitidas.

La raíz destino se recibe explícitamente por `root_path` o `project_id`; nunca se
deduce del cwd del proceso MCP, que puede ser el directorio del servidor y no el
proyecto desde el que el cliente invocó una tool.

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
from typing import Any

from higpertext_mcp import profile_client
from higpertext_mcp.gen.profile.v1 import profile_pb2

_WORKSPACE_DIR = ".higpertext"


def canonical_project_path(path: Path) -> Path:
    """Convierte una ruta visible dentro del MCP a la ruta host registrada."""
    path = path.expanduser().resolve()
    local_root_value = os.environ.get("HIGPERTEXT_PROJECT_ROOT")
    local_root = Path(local_root_value).expanduser() if local_root_value else None
    host_root = os.environ.get("HIGPERTEXT_HOST_PROJECT_ROOT")
    if host_root and local_root and path == local_root.resolve():
        return Path(host_root).expanduser().resolve()

    mount = os.environ.get("HIGPERTEXT_PROJECTS_MOUNT", "/projects")
    host_projects = os.environ.get("HIGPERTEXT_HOST_PROJECTS_ROOT")
    if host_projects:
        mount_path = Path(mount).expanduser().resolve()
        try:
            relative = path.relative_to(mount_path)
        except ValueError:
            pass
        else:
            return (Path(host_projects).expanduser().resolve() / relative).resolve()
    return path


def local_project_path(path: str | Path) -> Path:
    """Convierte una ruta canónica host a la ruta montada localmente."""
    path = Path(path).expanduser().resolve()
    local_root_value = os.environ.get("HIGPERTEXT_PROJECT_ROOT")
    local_root = Path(local_root_value).expanduser() if local_root_value else None
    host_root = os.environ.get("HIGPERTEXT_HOST_PROJECT_ROOT")
    if host_root and local_root and path == Path(host_root).expanduser().resolve():
        return local_root.resolve()

    mount = Path(os.environ.get("HIGPERTEXT_PROJECTS_MOUNT", "/projects")).expanduser().resolve()
    host_projects = os.environ.get("HIGPERTEXT_HOST_PROJECTS_ROOT")
    if host_projects:
        try:
            relative = path.relative_to(Path(host_projects).expanduser().resolve())
        except ValueError:
            pass
        else:
            return (mount / relative).resolve()
    return path


def resolve_project_root() -> Path:
    """Raíz configurada explícitamente para este proceso MCP.

    No usa ``cwd``: el cwd pertenece al proceso del servidor, no necesariamente
    al proyecto desde el que el cliente invocó una tool.
    """
    override = os.environ.get("HIGPERTEXT_PROJECT_ROOT")
    if not override:
        raise RuntimeError("no hay proyecto seleccionado; indique root_path o project_id")
    return Path(override).expanduser().resolve()


async def resolve_registered_project(*, root_path: str = "", project_id: str = "") -> tuple[Path, dict[str, Any]]:
    """Resuelve el proyecto destino exclusivamente contra ProjectService."""
    if root_path and project_id:
        raise ValueError("root_path y project_id son mutuamente excluyentes")
    if root_path:
        requested = canonical_project_path(Path(root_path))
        project = await profile_client.resolve_project(str(requested))
        paths = {Path(p).expanduser().resolve() for p in project.get("paths", [])}
        paths.add(Path(project["root_path"]).expanduser().resolve())
        if requested not in paths:
            raise ValueError("root_path no pertenece al proyecto resuelto")
        return local_project_path(requested), project
    if project_id:
        projects = await profile_client.list_projects()
        project = next((p for p in projects if p.get("id") == project_id), None)
        if project is None:
            raise ValueError(f"proyecto registrado no encontrado: {project_id}")
        return local_project_path(project["root_path"]), project
    raise ValueError("debe indicar root_path o project_id")


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
