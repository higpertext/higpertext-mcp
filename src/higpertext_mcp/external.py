"""Proxy hacia otros servidores MCP externos (stdio) — federación v1.

`higpertext-mcp` puede actuar simultáneamente como servidor MCP (hacia el
asistente) y como cliente MCP (hacia otros servidores declarados en
`.higpertext/config/mcp_external.json`), fusionando sus tools bajo el mismo
endpoint con el prefijo `external.<server>.<tool>`.

Alcance v1, deliberadamente acotado (ver plan): solo transporte stdio, sin
reconexión automática ni hot-add a mitad de sesión, sin `ContractValidator`
ni registro en `.memory/` para tools externas (no son capabilities propias).
Un servidor que falla al iniciar o revienta después nunca tumba el proceso
de higpertext-mcp — se omite/desaparece de `list_tools()`, siempre logueando
a stderr (nunca a stdout, rompería el protocolo stdio).
"""

from __future__ import annotations

import json
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path

import mcp.types as types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

_CONFIG_REL_PATH = Path(".higpertext") / "config" / "mcp_external.json"
_NAME_PREFIX = "external"


def _warn(message: str) -> None:
    print(f"[higpertext-mcp/external] {message}", file=sys.stderr)


@dataclass(frozen=True)
class ExternalServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_external_servers(root: Path) -> list[ExternalServerConfig]:
    """Lee y valida `.higpertext/config/mcp_external.json`. Fail-closed: [] en cualquier error."""
    data = _read_json(root / _CONFIG_REL_PATH)
    raw_servers = data.get("servers", []) if isinstance(data, dict) else []
    if not isinstance(raw_servers, list):
        return []

    configs: list[ExternalServerConfig] = []
    for entry in raw_servers:
        if not isinstance(entry, dict):
            _warn(f"entrada de servidor externo inválida (no es objeto): {entry!r}")
            continue
        name = entry.get("name")
        command = entry.get("command")
        if not name or not command:
            _warn(f"entrada de servidor externo sin 'name'/'command', omitida: {entry!r}")
            continue
        configs.append(
            ExternalServerConfig(
                name=name,
                command=command,
                args=list(entry.get("args", [])),
                env=entry.get("env"),
            )
        )
    return configs


def _prefixed_name(server_name: str, tool_name: str) -> str:
    return f"{_NAME_PREFIX}.{server_name}.{tool_name}"


class ExternalServerPool:
    """Administra sesiones MCP a servidores externos y fusiona/reenvía sus tools.

    `configs=[]` (default) la vuelve un no-op total, así `build_server()` sin
    pool sigue comportándose exactamente igual que antes de esta feature.
    """

    def __init__(self, configs: list[ExternalServerConfig] | None = None) -> None:
        self._configs = configs or []
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._route: dict[str, tuple[str, str]] = {}  # prefixed_name -> (server_name, real_name)

    @classmethod
    def from_sessions(cls, sessions: dict[str, ClientSession]) -> ExternalServerPool:
        """Constructor de testing: inyecta sesiones ya conectadas, sin spawnear nada."""
        pool = cls([])
        pool._sessions = dict(sessions)
        return pool

    async def start(self) -> None:
        for cfg in self._configs:
            try:
                params = StdioServerParameters(command=cfg.command, args=cfg.args, env=cfg.env)
                read, write = await self._stack.enter_async_context(stdio_client(params))
                session = await self._stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
            except Exception as exc:  # noqa: BLE001 — un servidor roto no debe tumbar el proceso
                _warn(f"servidor externo '{cfg.name}' no pudo iniciar: {exc}")
                continue
            self._sessions[cfg.name] = session

    async def list_tools_merged(self) -> list[types.Tool]:
        merged: list[types.Tool] = []
        route: dict[str, tuple[str, str]] = {}
        dead: list[str] = []

        for server_name, session in self._sessions.items():
            try:
                result = await session.list_tools()
            except Exception as exc:  # noqa: BLE001 — sesión caída no debe tumbar list_tools()
                _warn(f"servidor externo '{server_name}' no respondió list_tools(): {exc}")
                dead.append(server_name)
                continue
            for tool in result.tools:
                prefixed = _prefixed_name(server_name, tool.name)
                route[prefixed] = (server_name, tool.name)
                merged.append(
                    types.Tool(
                        name=prefixed,
                        description=f"[external:{server_name}] {tool.description or ''}".strip(),
                        inputSchema=tool.inputSchema,
                        annotations=tool.annotations,
                    )
                )

        for server_name in dead:
            self._sessions.pop(server_name, None)

        self._route = route
        return merged

    def has_tool(self, name: str) -> bool:
        if name in self._route:
            return True
        return self._resolve(name) is not None

    def _resolve(self, name: str) -> tuple[str, str] | None:
        """Resuelve `external.<server>.<real_name>` sin depender de un list_tools_merged() previo.

        Los nombres de servidor los definimos nosotros en la config (sin
        puntos garantizado en la práctica), así que partir con maxsplit=2
        es seguro incluso si `real_name` trae puntos propios.
        """
        parts = name.split(".", 2)
        if len(parts) != 3 or parts[0] != _NAME_PREFIX:
            return None
        server_name, real_name = parts[1], parts[2]
        if server_name not in self._sessions:
            return None
        return server_name, real_name

    async def call_tool(self, name: str, arguments: dict) -> types.CallToolResult:
        route = self._route.get(name) or self._resolve(name)
        if route is None:
            message = f"Unknown external tool: {name}"
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=message)],
                isError=True,
            )
        server_name, real_name = route
        session = self._sessions.get(server_name)
        if session is None:
            message = f"External server '{server_name}' is not connected."
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=message)],
                isError=True,
            )
        try:
            return await session.call_tool(real_name, arguments)
        except Exception as exc:  # noqa: BLE001 — el fallo debe volver como error MCP, no como excepción
            message = f"Error calling external tool '{name}': {exc}"
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=message)],
                isError=True,
            )

    async def aclose(self) -> None:
        await self._stack.aclose()
        self._sessions.clear()
        self._route.clear()

    async def __aenter__(self) -> ExternalServerPool:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
