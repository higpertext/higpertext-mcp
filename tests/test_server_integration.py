"""Valida el wire protocol real (no solo las funciones internas): levanta el
Server en memoria y lo habla con un ClientSession de verdad, como haría un
cliente MCP real (Claude Code u otro)."""

import json
import tempfile
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from higpertext_mcp import server as server_module


def _make_project(active_profile: str, capabilities: list[str]) -> Path:
    root = Path(tempfile.mkdtemp())
    config_dir = root / ".higpertext" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "environment.json").write_text(
        json.dumps({"active_profile": active_profile}), encoding="utf-8"
    )
    profiles_dir = root / "src" / "config" / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / f"{active_profile}.json").write_text(
        json.dumps({"capabilities": capabilities}), encoding="utf-8"
    )
    return root


@pytest.mark.anyio
async def test_list_tools_over_real_protocol(monkeypatch):
    root = _make_project("dev", ["common.grep-search", "git.diff"])
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))

    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_tools()
        names = {t.name for t in result.tools}
        assert names == {"common.grep-search", "git.diff"}
        grep_tool = next(t for t in result.tools if t.name == "common.grep-search")
        assert grep_tool.annotations.readOnlyHint is True
        assert "pattern" in grep_tool.inputSchema["properties"]


@pytest.mark.anyio
async def test_call_unknown_tool_returns_is_error(monkeypatch):
    root = _make_project("dev", ["common.grep-search"])
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))

    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("common.no-existe", {})
        assert result.isError is True


@pytest.mark.anyio
async def test_list_resources_exposes_usage(monkeypatch):
    root = _make_project("dev", [])
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))

    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_resources()
        uris = {str(r.uri) for r in result.resources}
        assert "higpertext://session/usage" in uris

        read = await client.read_resource("higpertext://session/usage")
        payload = json.loads(read.contents[0].text)
        assert payload == {"total_tokens": 0, "total_cost_usd": 0.0, "calls": 0, "by_tool": {}}
