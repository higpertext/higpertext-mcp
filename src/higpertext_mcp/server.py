"""Entrypoint del servidor MCP: registra una tool por cada capability permitida.

Usa `mcp.server.lowlevel.Server`, no `mcp.server.fastmcp.FastMCP` — FastMCP deriva
el inputSchema de los type hints de una función Python fija (`add_tool(fn, ...)`),
lo cual no sirve acá: el schema de cada tool viene de un JSON externo (`schema.py`)
resuelto en runtime, distinto por capability y por perfil activo. El API de bajo
nivel (`list_tools`/`call_tool` como handlers explícitos) es el que soporta eso.
"""

from __future__ import annotations

import asyncio
import sys

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from higpertext_mcp import discovery, dispatch, schema

SERVER_NAME = "higpertext-mcp"


def _load_tools() -> dict[str, schema.ToolSpec]:
    """Perfil activo del proyecto ∩ set fijo de v1 → specs cargadas desde sus JSON.

    Fail-closed: una capability permitida por perfil pero sin JSON legible se
    omite (no crashea el server ni expone una tool rota).
    """
    root = discovery.resolve_project_root()
    tools: dict[str, schema.ToolSpec] = {}
    for capability_id in discovery.allowed_capability_ids(root):
        spec = schema.load_tool_spec(capability_id)
        if spec is not None:
            tools[capability_id] = spec
    return tools


def build_server() -> Server:
    server = Server(SERVER_NAME)
    tools = _load_tools()

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=capability_id,
                description=spec.description,
                inputSchema=spec.input_schema,
            )
            for capability_id, spec in tools.items()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name not in tools:
            return [types.TextContent(type="text", text=f"[ERROR] tool desconocida: {name}")]
        result = dispatch.call_capability(name, arguments)
        prefix = "" if result.ok else "[ERROR] "
        return [types.TextContent(type="text", text=f"{prefix}{result.output}")]

    return server


async def _amain() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    run()
