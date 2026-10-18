"""Tool interna higpertext-dashboard: acciones, validación y contrato de resultado."""

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from dashboard_stub import api, api_token, provider  # noqa: F401 — fixtures
from higpertext_mcp import dashboard_tool, server as server_module
from test_server_integration import _make_project, _stub_profile_catalog

CONTRACT_KEYS = {"ok", "summary", "data", "artifacts", "warnings", "error"}
SETTINGS_V2 = {"schemaVersion": 2, "uid": "u1", "panels": []}


async def call(args, token=None):
    return await dashboard_tool.run(args, token or api_token())


@pytest.mark.anyio
async def test_schema_templates_template_validate_actions(api):
    api.queue(200, {"$id": "dashboard.v2"})
    result = await call({"action": "schema"})
    assert result["ok"] and result["data"] == {"schema": {"$id": "dashboard.v2"}}
    assert (api.requests[-1]["method"], api.requests[-1]["path"]) == ("GET", "/api/dashboards/schema")

    api.queue(200, [{"name": "agent-ops", "title": "Operación", "description": "d"}])
    result = await call({"action": "templates"})
    assert result["ok"] and result["data"]["templates"][0]["name"] == "agent-ops"
    assert api.requests[-1]["path"] == "/api/dashboards/templates"

    api.queue(200, {"title": "Operación", "description": "d", "settings": SETTINGS_V2})
    result = await call({"action": "template", "name": "agent-ops"})
    assert result["ok"] and result["data"]["name"] == "agent-ops" and result["data"]["settings"] == SETTINGS_V2
    assert api.requests[-1]["path"] == "/api/dashboards/templates/agent-ops"

    api.queue(200, {"valid": True, "schemaVersion": 2, "settings": SETTINGS_V2})
    result = await call({"action": "validate", "settings": SETTINGS_V2})
    assert result["ok"] and result["data"]["valid"] is True and result["data"]["schemaVersion"] == 2
    assert (api.requests[-1]["method"], api.requests[-1]["path"]) == ("POST", "/api/dashboards/validate")
    assert api.requests[-1]["body"] == {"settings": SETTINGS_V2}
    assert all(r["headers"]["x-htx-on-behalf-of"] == "user-1" for r in api.requests)


@pytest.mark.anyio
async def test_list_get_export_actions(api):
    api.queue(200, [{"id": "d1", "title": "A", "scope": "personal", "version": 2, "settings": SETTINGS_V2, "ownerSub": "no-debe-salir"}])
    result = await call({"action": "list", "scope": "shared"})
    assert (api.requests[-1]["method"], api.requests[-1]["path"], api.requests[-1]["query"]) == ("GET", "/api/dashboards", {"scope": "shared"})
    item = result["data"]["dashboards"][0]
    assert item["id"] == "d1" and "settings" not in item and "ownerSub" not in item
    assert result["data"]["total"] == 1 and result["data"]["truncated"] is False

    api.queue(200, [{"id": "d1", "title": "A", "settings": SETTINGS_V2}])
    with_settings = await call({"action": "list", "include_settings": True})
    assert with_settings["data"]["dashboards"][0]["settings"] == SETTINGS_V2
    assert api.requests[-1]["query"] == {}

    api.queue(200, {"id": "d1", "title": "A", "version": 3, "settings": SETTINGS_V2})
    got = await call({"action": "get", "id": "d1"})
    assert got["ok"] and got["data"]["dashboard"]["version"] == 3
    assert (api.requests[-1]["path"], api.requests[-1]["query"]) == ("/api/dashboards/d1", {"format": "v2"})
    api.queue(200, {"id": "d1", "title": "A", "version": 3, "settings": {"filters": {}}})
    await call({"action": "get", "id": "d1", "format": "v1"})
    assert api.requests[-1]["query"] == {"format": "v1"}

    api.queue(200, {"title": "A", "description": "", "settings": SETTINGS_V2})
    exported = await call({"action": "export", "id": "d1"})
    assert exported["data"]["export"]["settings"] == SETTINGS_V2
    assert api.requests[-1]["path"] == "/api/dashboards/d1/export"


@pytest.mark.anyio
async def test_versions_version_get_restore_actions(api):
    api.queue(200, [{"version": 3}, {"version": 2}, {"version": 1}])
    versions = await call({"action": "versions", "id": "d1"})
    assert [v["version"] for v in versions["data"]["versions"]] == [3, 2, 1]
    assert api.requests[-1]["path"] == "/api/dashboards/d1/versions"

    api.queue(200, {"version": 2, "title": "T", "settings": SETTINGS_V2})
    snapshot = await call({"action": "version_get", "id": "d1", "version": 2})
    assert snapshot["data"]["version_snapshot"]["version"] == 2
    assert api.requests[-1]["path"] == "/api/dashboards/d1/versions/2"

    api.queue(200, {"id": "d1", "version": 4, "settings": SETTINGS_V2})
    restored = await call({"action": "restore", "id": "d1", "version": 2})
    assert restored["ok"] and restored["data"]["dashboard"]["version"] == 4
    assert (api.requests[-1]["method"], api.requests[-1]["path"], api.requests[-1]["body"]) == ("POST", "/api/dashboards/d1/versions/2/restore", None)

    api.queue(200, {"id": "d1", "version": 5, "settings": SETTINGS_V2})
    await call({"action": "restore", "id": "d1", "version": 2, "expected_version": 4})
    assert api.requests[-1]["body"] == {"version": 4}


@pytest.mark.anyio
async def test_import_passes_provisioned_and_returns_action(api):
    dashboard = {"id": "d9", "title": "Ops", "version": 1, "provisioned": True, "settings": SETTINGS_V2}
    api.queue(201, {"action": "created", "dashboard": dashboard})
    result = await call({"action": "import", "title": "Ops", "description": "desc", "settings": SETTINGS_V2, "provisioned": True})
    assert result["ok"] and result["data"]["action"] == "created"
    assert "settings" not in result["data"]["dashboard"] and result["data"]["dashboard"]["id"] == "d9"
    request = api.requests[-1]
    assert (request["method"], request["path"]) == ("POST", "/api/dashboards/import")
    assert request["body"] == {"title": "Ops", "description": "desc", "settings": SETTINGS_V2, "provisioned": True}

    for action in ("unchanged", "updated"):
        api.queue(200, {"action": action, "dashboard": dashboard})
        again = await call({"action": "import", "title": "Ops", "settings": SETTINGS_V2})
        assert again["data"]["action"] == action
        assert api.requests[-1]["body"]["provisioned"] is False and api.requests[-1]["body"]["description"] == ""


@pytest.mark.anyio
async def test_query_translates_arguments_to_camel_case_body(api):
    api.queue(200, {"results": {"A": {"status": 200, "frames": []}, "B": {"status": 503, "error": {"code": "upstream_unavailable"}}},
                    "variables": {"p": {"values": ["dev"]}}, "meta": {"intervalMs": 72000}})
    target = {"refId": "A", "datasource": "agent", "query": {"entity": "session"}}
    result = await call({
        "action": "query", "project_id": "p1", "targets": [target], "time": {"from": "now-1h", "to": "now"},
        "variables": {"profile": "dev"}, "max_data_points": 120,
        "variable_queries": [{"name": "p", "query": {"entity": "session", "values": "profile"}}],
    })
    body = api.requests[-1]["body"]
    assert (api.requests[-1]["method"], api.requests[-1]["path"]) == ("POST", "/api/dashboards/query")
    assert body == {
        "projectId": "p1", "targets": [target], "time": {"from": "now-1h", "to": "now"}, "variables": {"profile": "dev"},
        "maxDataPoints": 120, "variableQueries": [{"name": "p", "query": {"entity": "session", "values": "profile"}}],
    }
    assert not {"project_id", "max_data_points", "variable_queries"} & set(body)
    assert result["ok"] and result["data"]["results"]["A"]["status"] == 200 and "1 con error" in result["summary"]
    api.queue(200, {"results": {}})
    await call({"action": "query", "project_id": "p1", "targets": [target]})
    assert api.requests[-1]["body"] == {"projectId": "p1", "targets": [target]}


@pytest.mark.anyio
async def test_every_result_has_uniform_contract(api):
    api.queue(200, {"schema": 1}).queue(404, raw=b"no existe").queue(200, [])
    results = [
        await call({"action": "schema"}),
        await call({"action": "get", "id": "nope"}),
        await call({"action": "list"}),
        await call({"action": "nope"}),
        await call({"action": "import", "title": "x"}),
        await dashboard_tool.run({"action": "schema"}, None),
    ]
    assert [r["ok"] for r in results] == [True, False, True, False, False, False]
    for result in results:
        assert set(result) == CONTRACT_KEYS
        assert isinstance(result["summary"], str) and result["summary"]
        assert isinstance(result["data"], dict) and result["artifacts"] == [] and isinstance(result["warnings"], list)
        assert (result["error"] is None) == result["ok"]
        json.dumps(result)  # serializable


@pytest.mark.anyio
async def test_dashboard_tool_registered_with_schema_and_annotations(monkeypatch):
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(_make_project("dev")))
    _stub_profile_catalog(monkeypatch, {"dev": []})
    tool = server_module._DASHBOARD_TOOL
    assert tool.name == "higpertext-dashboard" == server_module.DASHBOARD_TOOL_NAME
    assert tool.inputSchema["properties"]["action"]["enum"] == [
        "schema", "templates", "template", "validate", "list", "get", "export", "versions", "version_get",
        "import", "restore", "delete", "query",
    ]
    assert len(tool.inputSchema["properties"]["action"]["enum"]) == 13
    assert tool.inputSchema["additionalProperties"] is False and tool.inputSchema["required"] == ["action"]
    assert tool.annotations.destructiveHint is True and tool.annotations.readOnlyHint is False
    assert "on_behalf_of" not in tool.inputSchema["properties"]  # la delegación nunca sale de los argumentos
    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        listed = {t.name: t for t in (await client.list_tools()).tools}
    assert "higpertext-dashboard" in listed
    assert listed["higpertext-dashboard"].inputSchema == tool.inputSchema


@pytest.mark.anyio
async def test_invalid_arguments_are_rejected_before_any_request(api):
    bad = [
        {"action": "frobnicate"},
        {"action": "import", "title": "sin settings"},
        {"action": "import", "settings": SETTINGS_V2},
        {"action": "get"},
        {"action": "template"},
        {"action": "validate"},
        {"action": "version_get", "id": "d1", "version": 0},
        {"action": "restore", "id": "d1", "version": -1},
        {"action": "restore", "id": "d1"},
        {"action": "query", "targets": []},
        {"action": "list", "limit": 101},
        {"action": "get", "id": "d1", "format": "v3"},
        {"action": "get", "id": "../projects"},
        {"action": "schema", "on_behalf_of": "otro-usuario"},
        {},
    ]
    for arguments in bad:
        result = await call(arguments)
        assert result["ok"] is False and result["error"], arguments
    assert api.requests == []


@pytest.mark.anyio
async def test_delete_requires_confirm_and_sends_delete(api):
    for arguments in ({"action": "delete", "id": "d1"}, {"action": "delete", "id": "d1", "confirm": False}):
        refused = await call(arguments)
        assert refused["ok"] is False and "confirm" in refused["summary"]
    assert api.requests == []
    api.queue(204, raw=b"")
    deleted = await call({"action": "delete", "id": "d1", "confirm": True})
    assert deleted["ok"] and deleted["data"] == {"deleted": True, "id": "d1"}
    assert (api.requests[-1]["method"], api.requests[-1]["path"]) == ("DELETE", "/api/dashboards/d1")


@pytest.mark.anyio
async def test_token_without_user_id_is_refused_without_request(api):
    for token in (None, api_token(user_id="")):
        result = await dashboard_tool.run({"action": "list"}, token)
        assert result["ok"] is False and "PAT" in result["summary"] and set(result) == CONTRACT_KEYS
    assert api.requests == []


@pytest.mark.anyio
async def test_server_errors_propagate_status_and_code(api):
    cases = [
        (400, b"settings inv\xc3\xa1lidos", 400, "bad_request", None),
        (403, json.dumps({"error": {"code": "forbidden", "message": "sin permiso"}}).encode(), 403, "forbidden", None),
        (404, b"404 page not found", 404, "not_found", None),
        (409, json.dumps({"error": "conflicto de versión", "currentVersion": 4}).encode(), 409, "conflict", 4),
        (409, json.dumps({"error": "dashboard provisionado: actualizalo con POST /api/dashboards/import"}).encode(), 409, "conflict", None),
        (500, b"boom", 500, "server_error", None),
    ]
    for status, raw, want_status, want_code, current in cases:
        api.queue(status, raw=raw)
        result = await call({"action": "import", "title": "x", "settings": SETTINGS_V2})
        assert result["ok"] is False
        assert result["data"]["status"] == want_status and result["data"]["code"] == want_code
        assert str(want_status) in result["summary"] and result["error"] == result["summary"]
        assert result["data"].get("currentVersion") == current
    api.queue(403, raw=json.dumps({"error": "svc-token-1 Bearer svc-token-1"}).encode())
    leaked = await call({"action": "list"})
    assert "svc-token-1" not in json.dumps(leaked)


@pytest.mark.anyio
async def test_large_outputs_are_bounded(api):
    items = [{"id": f"d{i}", "title": f"Dashboard {i}", "version": 1} for i in range(60)]
    api.queue(200, items)
    listed = await call({"action": "list"})
    assert len(listed["data"]["dashboards"]) == dashboard_tool.LIST_DEFAULT_LIMIT == 50
    assert listed["data"]["total"] == 60 and listed["data"]["truncated"] is True and listed["warnings"]
    api.queue(200, items)
    assert len((await call({"action": "list", "limit": 100}))["data"]["dashboards"]) == 60

    huge = {"id": "d1", "title": "Enorme", "settings": {"schemaVersion": 2, "panels": [], "filters": {"x": "y" * 100_000}}}
    api.queue(200, huge)
    result = await call({"action": "get", "id": "d1"})
    assert result["ok"] is True and result["data"]["truncated"] is True and result["data"]["bytes"] > dashboard_tool.MAX_DATA_BYTES
    assert result["warnings"] and len(json.dumps(result)) < dashboard_tool.MAX_DATA_BYTES
