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

import contextvars
import json
import os
from pathlib import Path
from typing import Any

from higpertext_mcp import profile_client
from higpertext_mcp.gen.profile.v1 import profile_pb2

_WORKSPACE_DIR = ".higpertext"

# Header con el que cada cliente declara la raíz host de su proyecto.
PROJECT_ROOT_HEADER = "X-Higpertext-Project-Root"
_request_root: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "higpertext_request_root", default=None
)


def _configured_allowed_roots() -> tuple[Path, ...]:
    """Lee límites de filesystem administrados por la instancia MCP.

    El valor es opcional para conservar compatibilidad con stdio local. En
    HTTP/Docker se recomienda configurarlo con rutas host canónicas separadas
    por ``os.pathsep``; nunca debe venir de argumentos del caller.
    """
    raw = os.environ.get("HIGPERTEXT_ALLOWED_PROJECT_ROOTS", "")
    if not raw.strip():
        return ()
    return tuple(Path(item).expanduser().resolve() for item in raw.split(os.pathsep) if item.strip())


def _validate_allowed_root(path: Path) -> Path:
    allowed = _configured_allowed_roots()
    if not allowed:
        return path
    if not any(path == root or root in path.parents for root in allowed):
        raise ValueError("la ruta del proyecto está fuera de las raíces autorizadas")
    return path


def canonical_project_path(path: Path) -> Path:
    """Convierte una ruta visible dentro del MCP a la ruta host registrada."""
    path = path.expanduser().resolve()
    local_root_value = os.environ.get("HIGPERTEXT_PROJECT_ROOT")
    local_root = Path(local_root_value).expanduser() if local_root_value else None
    host_root = os.environ.get("HIGPERTEXT_HOST_PROJECT_ROOT")
    if host_root and local_root and path == local_root.resolve():
        return _validate_allowed_root(Path(host_root).expanduser().resolve())

    mount = os.environ.get("HIGPERTEXT_PROJECTS_MOUNT", "/projects")
    host_projects = os.environ.get("HIGPERTEXT_HOST_PROJECTS_ROOT")
    if host_projects:
        mount_path = Path(mount).expanduser().resolve()
        try:
            relative = path.relative_to(mount_path)
        except ValueError:
            pass
        else:
            return _validate_allowed_root((Path(host_projects).expanduser().resolve() / relative).resolve())
    return _validate_allowed_root(path)


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


def select_request_project(host_root: str) -> contextvars.Token:
    """Fija la raíz del proyecto para el request actual (selector explícito).

    El gateway HTTP es compartido por todos los proyectos del host; el cliente
    declara su raíz host en el header ``PROJECT_ROOT_HEADER`` (lo escribe
    ``adapter_renderer`` en `.mcp.json`). Se traduce al path montado y se
    valida contra las raíces autorizadas. Una raíz inexistente falla — nunca
    cae a la raíz del proceso, que es otro proyecto.
    """
    local = local_project_path(_validate_allowed_root(Path(host_root).expanduser().resolve()))
    if not local.is_dir():
        raise ValueError(f"raíz de proyecto no visible para el MCP: {host_root}")
    return _request_root.set(local)


def reset_request_project(token: contextvars.Token) -> None:
    _request_root.reset(token)


def mcp_client_headers(root: Path) -> dict[str, str]:
    """Headers que el cliente MCP del proyecto debe enviar al gateway HTTP."""
    return {PROJECT_ROOT_HEADER: str(canonical_project_path(root))}


def resolve_project_root() -> Path:
    """Raíz seleccionada explícitamente: la del request, o la del proceso MCP.

    No usa ``cwd``: el cwd pertenece al proceso del servidor, no necesariamente
    al proyecto desde el que el cliente invocó una tool.
    """
    selected = _request_root.get()
    if selected is not None:
        return selected
    override = os.environ.get("HIGPERTEXT_PROJECT_ROOT")
    if not override:
        raise RuntimeError("no hay proyecto seleccionado; indique root_path o project_id")
    return _validate_allowed_root(Path(override).expanduser().resolve())


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
        registered_root = _validate_allowed_root(Path(project["root_path"]).expanduser().resolve())
        return local_project_path(registered_root), project
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
