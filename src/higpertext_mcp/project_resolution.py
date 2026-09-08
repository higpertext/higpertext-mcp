"""Resolución centralizada y cacheada de Project.id (tenancy.db) para una raíz física.

Antes esto vivía duplicado y solo se resolvía al cierre de sesión
(`hook_session_stop._resolve_project_id`, gRPC síncrono ad-hoc). Ahora se
resuelve una única vez al abrir sesión (`hook_session_prompt`) y se cachea en
`.higpertext/state/session.json` bajo la clave `project` — cualquier
hook/capability que necesite `project_id` lo lee de ahí primero
(`cached_project_id`), sin gRPC extra por invocación.

Fail-open en toda esta capa: sin profile-server disponible, `resolve_project`
devuelve `None` y el caller sigue funcionando sin `project_id` — nunca debe
tumbar la sesión ni el hook que lo invoca.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TypedDict

WORKSPACE_DIR_NAME = ".higpertext"


class ResolvedProject(TypedDict):
    id: str
    name: str
    root_path: str
    paths: list[str]


def _session_path(root: Path) -> Path:
    return root / WORKSPACE_DIR_NAME / "state" / "session.json"


def resolve_project(root: Path) -> ResolvedProject | None:
    """Resuelve (o crea) el Project vía ProjectService.ResolveProject (tenancy.db).

    Best-effort y síncrono a propósito — se llama desde hooks que no corren
    dentro de un event loop asyncio. `None` si el profile-server no responde
    o el paquete gRPC no está disponible; nunca lanza.
    """
    try:
        import higpertext_mcp

        sys.path.insert(0, str(Path(higpertext_mcp.__file__).parent / "gen"))
        from higpertext_mcp.gen.profile.v1 import profile_pb2, profile_pb2_grpc
        import grpc as _grpc
    except ImportError:
        return None

    addr = os.environ.get("HIGPERTEXT_PROFILE_SERVER_ADDR", "localhost:50051")
    try:
        channel = _grpc.insecure_channel(addr)
        stub = profile_pb2_grpc.ProjectServiceStub(channel)
        resp = stub.ResolveProject(profile_pb2.ResolveProjectRequest(root_path=str(root)), timeout=2)
        channel.close()
        return {
            "id": resp.project.id, "name": resp.project.name, "root_path": resp.project.root_path,
            "paths": list(resp.project.paths),
        }
    except Exception:  # noqa: BLE001 — best-effort, un profile server caído nunca debe tumbar al caller
        return None


def cached_project_id(root: Path) -> str:
    """Lee `project.id` desde session.json si ya quedó cacheado — sin gRPC.

    "" si no hay sesión activa, si nunca se resolvió project_id (ej. sesión
    vieja de antes de este cambio, o profile-server caído al abrir sesión),
    o si el archivo está corrupto/ausente.
    """
    try:
        data = json.loads(_session_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return data.get("project", {}).get("id", "")
