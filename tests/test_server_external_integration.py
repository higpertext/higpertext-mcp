"""Integración real de la federación MCP: un servidor 'externo' de juguete
(hablado por un ClientSession real en memoria, sin subprocess) inyectado en
una ExternalServerPool, y el build_server() real de higpertext hablado por
otro ClientSession real — igual patrón que test_server_integration.py."""

import json
import tempfile
from pathlib import Path

import mcp.types as types
import pytest
from mcp.server.lowlevel import Server
from mcp.shared.memory import create_connected_server_and_client_session

from higpertext_mcp import discovery, external, server as server_module
from higpertext_mcp.gen.profile.v1 import profile_pb2


def _make_project(active_profile: str) -> Path:
    root = Path(tempfile.mkdtemp())
    config_dir = root / ".higpertext" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "environment.json").write_text(
        json.dumps({"active_profile": active_profile}), encoding="utf-8"
    )
    return root


_GREP_SEARCH = profile_pb2.Capability(id="common.grep-search")


def _stub_profile_catalog(
    monkeypatch, profile_to_capabilities: dict[str, list[profile_pb2.Capability]]
) -> None:
    async def fake_list_allowed(profile):
        return profile_to_capabilities.get(profile, [])

    monkeypatch.setattr(discovery.profile_client, "list_allowed_capabilities", fake_list_allowed)


def _build_toy_external_server() -> Server:
    toy = Server("toy-external")

    @toy.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="echo",
                description="Repite el texto recibido.",
                inputSchema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            )
        ]

    @toy.call_tool()
    async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
        if name != "echo":
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Unknown: {name}")],
                isError=True,
            )
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=arguments.get("text", ""))],
            isError=False,
        )

    return toy


@pytest.mark.anyio
async def test_external_tool_appears_prefixed_and_is_callable(monkeypatch):
    root = _make_project("dev")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))
    _stub_profile_catalog(monkeypatch, {"dev": [_GREP_SEARCH]})

    toy_server = _build_toy_external_server()
    async with create_connected_server_and_client_session(toy_server) as toy_session:
        pool = external.ExternalServerPool.from_sessions({"toy": toy_session})

        real_server = server_module.build_server(pool)
        async with create_connected_server_and_client_session(real_server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools.tools}
            assert "common-grep-search" in names
            assert "external.toy.echo" in names

            echo_tool = next(t for t in tools.tools if t.name == "external.toy.echo")
            assert echo_tool.description.startswith("[external:toy]")

            result = await client.call_tool("external.toy.echo", {"text": "hola"})
            assert result.isError is False
            assert result.content[0].text == "hola"


@pytest.mark.anyio
async def test_local_and_external_names_never_collide(monkeypatch):
    root = _make_project("dev")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))
    _stub_profile_catalog(monkeypatch, {"dev": [_GREP_SEARCH]})

    toy_server = _build_toy_external_server()
    async with create_connected_server_and_client_session(toy_server) as toy_session:
        # Nombra el servidor externo igual que un namespace local ('common') a propósito:
        # el prefijo 'external.' evita cualquier colisión con capability ids reales.
        pool = external.ExternalServerPool.from_sessions({"common": toy_session})
        real_server = server_module.build_server(pool)
        async with create_connected_server_and_client_session(real_server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools.tools}
            assert "common-grep-search" in names
            assert "external.common.echo" in names
            assert len(names) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
