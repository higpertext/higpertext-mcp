"""Permisos, filtrado de acciones y exposición de higpertext-dashboard."""

import tempfile
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from dashboard_stub import api, api_token, provider  # noqa: F401 — fixtures
from higpertext_mcp import profile_client, server as server_module, token_permissions
from test_server_integration import _make_project, _stub_profile_catalog

READS = ["schema", "templates", "template", "validate", "list", "get", "export", "versions", "version_get"]
WRITES = ["import", "restore", "delete"]


def _as_token(monkeypatch, token):
    monkeypatch.setattr(server_module, "current_api_token", lambda: token)


def test_required_permission_maps_every_dashboard_action():
    for action in READS:
        assert token_permissions.required_permission("higpertext-dashboard", action) == "projects.view", action
    for action in WRITES:
        assert token_permissions.required_permission("higpertext-dashboard", action) == "projects.edit", action
    assert token_permissions.required_permission("higpertext-dashboard", "query") == "audit.view"
    # Fail-closed: una acción desconocida o vacía no se mapea a ningún permiso.
    for action in ("", "frobnicate", "duplicate", "shares", "order"):
        assert token_permissions.required_permission("higpertext-dashboard", action) is None, action
    assert set(READS + WRITES + ["query"]) == set(server_module._DASHBOARD_TOOL.inputSchema["properties"]["action"]["enum"])
    # El mapeo no cambió el de las otras tools.
    assert token_permissions.required_permission("higpertext-roadmap-board", "overview") == "boards.view"


def test_filtered_tool_exposes_only_authorized_actions():
    tool = server_module._DASHBOARD_TOOL

    def actions(*scopes):
        visible = token_permissions.filtered_tool(tool, api_token(scopes=scopes))
        return None if visible is None else visible.inputSchema["properties"]["action"]["enum"]

    assert set(actions("projects.view")) == set(READS)
    assert set(actions("projects.edit")) == set(WRITES)
    assert set(actions("audit.view")) == {"query"}
    assert set(actions("lectura")) == set(READS + ["query"]) and len(actions("lectura")) == 10
    assert set(actions("administración")) == set(READS + WRITES + ["query"]) and len(actions("administración")) == 13
    assert set(actions("projects.view", "projects.edit")) == set(READS + WRITES)
    assert actions("boards.view") is None, "sin ningún permiso de dashboards la tool se oculta"
    assert actions() is None
    # El filtrado trabaja sobre una copia: la tool declarada no cambia.
    assert len(tool.inputSchema["properties"]["action"]["enum"]) == 13


@pytest.mark.anyio
async def test_dashboard_tool_listed_regardless_of_active_profile(monkeypatch):
    # Perfil activo que NO incluye la tool: las tools internas no dependen del perfil.
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(_make_project("dev")))
    _stub_profile_catalog(monkeypatch, {"dev": []})
    _as_token(monkeypatch, None)
    async with create_connected_server_and_client_session(server_module.build_server()) as client:
        assert "higpertext-dashboard" in {t.name for t in (await client.list_tools()).tools}

    # Sin perfil activo legible (fail-closed para capabilities): la tool interna sigue listada.
    empty = Path(tempfile.mkdtemp())
    (empty / ".higpertext" / "config").mkdir(parents=True)
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(empty))
    async with create_connected_server_and_client_session(server_module.build_server()) as client:
        assert "higpertext-dashboard" in {t.name for t in (await client.list_tools()).tools}

    # Con un PAT, aparece solo si algún scope cubre alguna acción.
    _as_token(monkeypatch, api_token(scopes=("projects.view",)))
    async with create_connected_server_and_client_session(server_module.build_server()) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        assert set(tools["higpertext-dashboard"].inputSchema["properties"]["action"]["enum"]) == set(READS)
    _as_token(monkeypatch, api_token(scopes=("boards.view",)))
    async with create_connected_server_and_client_session(server_module.build_server()) as client:
        assert "higpertext-dashboard" not in {t.name for t in (await client.list_tools()).tools}


@pytest.mark.anyio
async def test_call_denied_when_action_not_granted(monkeypatch, api):
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(_make_project("dev")))
    _stub_profile_catalog(monkeypatch, {"dev": []})
    _as_token(monkeypatch, api_token(scopes=("projects.view",)))
    settings = {"schemaVersion": 2, "uid": "u1", "panels": []}
    async with create_connected_server_and_client_session(server_module.build_server()) as client:
        denied = await client.call_tool("higpertext-dashboard", {"action": "import", "title": "x", "settings": settings})
        assert denied.isError is True
        assert "El token no tiene permiso" in denied.content[0].text
        for action in ({"action": "delete", "id": "d1", "confirm": True}, {"action": "restore", "id": "d1", "version": 1},
                       {"action": "query", "project_id": "p1", "targets": []}):
            assert (await client.call_tool("higpertext-dashboard", action)).isError is True
        assert api.requests == [], "una acción no concedida no llega a rules-api"

        api.queue(200, {"$id": "dashboard.v2"})
        allowed = await client.call_tool("higpertext-dashboard", {"action": "schema"})
        assert allowed.isError is False and allowed.structuredContent["ok"] is True
        assert allowed.structuredContent["_higpertext_auth"] == {"user_id": "user-1", "source": "validated_pat"}
    assert [r["path"] for r in api.requests] == ["/api/dashboards/schema"]
    assert api.requests[0]["headers"]["x-htx-on-behalf-of"] == "user-1"


@pytest.mark.anyio
async def test_stdio_without_pat_lists_tool_but_call_is_refused_clearly(monkeypatch, api):
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(_make_project("dev")))
    _stub_profile_catalog(monkeypatch, {"dev": []})
    _as_token(monkeypatch, None)
    async with create_connected_server_and_client_session(server_module.build_server()) as client:
        assert "higpertext-dashboard" in {t.name for t in (await client.list_tools()).tools}
        result = await client.call_tool("higpertext-dashboard", {"action": "schema"})
    assert result.isError is True
    assert result.structuredContent["ok"] is False
    assert "PAT" in result.structuredContent["summary"] and "stdio" in result.structuredContent["summary"]
    assert api.requests == []


@pytest.mark.anyio
async def test_repository_limited_pat_scopes_query_by_project_id(monkeypatch, api):
    async def list_projects():
        return [{"id": "p1", "name": "uno"}, {"id": "p2", "name": "dos"}]

    async def list_repositories():
        return [{"id": "repo-1", "project_id": "p1"}, {"id": "repo-2", "project_id": "p2"}]

    monkeypatch.setattr(profile_client, "list_projects", list_projects)
    monkeypatch.setattr(profile_client, "list_repositories", list_repositories)
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(_make_project("dev")))
    _stub_profile_catalog(monkeypatch, {"dev": []})
    _as_token(monkeypatch, api_token(scopes=("audit.view", "projects.view"), repository_ids=("repo-1",)))
    target = {"refId": "A", "datasource": "prometheus", "expr": "up"}
    async with create_connected_server_and_client_session(server_module.build_server()) as client:
        assert "higpertext-dashboard" in {t.name for t in (await client.list_tools()).tools}

        api.queue(200, {"results": {"A": {"status": 200, "frames": []}}})
        own = await client.call_tool("higpertext-dashboard", {"action": "query", "project_id": "p1", "targets": [target]})
        assert own.isError is False and len(api.requests) == 1

        foreign = await client.call_tool("higpertext-dashboard", {"action": "query", "project_id": "p2", "targets": [target]})
        assert foreign.isError is True and "El token no tiene permiso" in foreign.content[0].text
        assert len(api.requests) == 1, "un proyecto fuera de los repositorios del PAT no llega a rules-api"

        unknown = await client.call_tool("higpertext-dashboard", {"action": "query", "project_id": "p-inexistente", "targets": [target]})
        assert unknown.isError is True and len(api.requests) == 1

        # Sin project_id la tool misma rechaza (no es un problema de permisos) y no hace ningún request.
        missing = await client.call_tool("higpertext-dashboard", {"action": "query", "targets": [target]})
        assert missing.isError is True and "project_id" in missing.structuredContent["summary"]
        assert "El token no tiene permiso" not in missing.content[0].text
        assert len(api.requests) == 1

        # Las acciones sin project_id son del usuario, no del repositorio: pasan.
        api.queue(200, [])
        listing = await client.call_tool("higpertext-dashboard", {"action": "list"})
        assert listing.isError is False and len(api.requests) == 2
