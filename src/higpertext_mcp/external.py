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
from mcp.client.streamable_http import streamable_http_client

_CONFIG_REL_PATH = Path(".higpertext") / "config" / "mcp_external.json"
_NAME_PREFIX = "external"


def _warn(message: str) -> None:
    print(f"[higpertext-mcp/external] {message}", file=sys.stderr)


@dataclass(frozen=True)
class ExternalServerConfig:
    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    transport: str = "stdio"
    url: str | None = None


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
        transport = entry.get("transport", "stdio")
        command = entry.get("command")
        url = entry.get("url")
        valid = (
            bool(name)
            and transport in {"stdio", "http"}
            and ((transport == "stdio" and bool(command)) or (transport == "http" and bool(url)))
        )
        if not valid:
            _warn(f"entrada de servidor externo inválida, omitida: {entry!r}")
            continue
        configs.append(
            ExternalServerConfig(
                name=name,
                command=command,
                args=list(entry.get("args", [])),
                env=entry.get("env"),
                transport=transport,
                url=url,
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
            # Stack por-servidor, no el compartido self._stack: si la
            # conexión falla a mitad de camino (streamable_http_client ya
            # entrado, ClientSession no), un __aenter__ roto queda igual
            # registrado ahí y vuelve a explotar más tarde al cerrar TODO
            # el pool (aclose -> self._stack.aclose()), aunque acá ya lo
            # hayamos "atrapado" — un servidor roto tumbaría el shutdown
            # entero. Cerrando su propio stack en el momento, el fallo
            # queda contenido a este server y no contamina a los demás.
            server_stack = AsyncExitStack()
            try:
                if cfg.transport == "http":
                    if not cfg.url:
                        raise ValueError("HTTP external server requires url")
                    read, write, _ = await server_stack.enter_async_context(streamable_http_client(cfg.url))
                else:
                    if not cfg.command:
                        raise ValueError("stdio external server requires command")
                    params = StdioServerParameters(command=cfg.command, args=cfg.args, env=cfg.env)
                    read, write = await server_stack.enter_async_context(stdio_client(params))
                session = await server_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
            except BaseException as exc:  # noqa: BLE001 — un servidor roto no debe tumbar el proceso
                # BaseException a propósito, no Exception: una conexión
                # fallida (DNS, connection refused) hace que la task group
                # interna de anyio (streamable_http_client / ClientSession)
                # levante un asyncio.CancelledError o un BaseExceptionGroup
                # envolviéndolo — ninguno de los dos hereda de Exception
                # desde Python 3.8/3.11. Con `except Exception` esto se
                # escapaba entero, tumbando el arranque de TODO
                # higpertext-mcp por un solo server externo caído (visto
                # con "telemetry"/"controller" apagados). El scope acá es
                # sólo "intentar conectar un server" dentro del for, así
                # que atrapar BaseException no esconde una cancelación real
                # del proceso — el loop sigue con el próximo cfg y termina
                # en el mismo tick.
                _warn(f"servidor externo '{cfg.name}' no pudo iniciar: {exc!r}")
                try:
                    await server_stack.aclose()
                except BaseException as close_exc:  # noqa: BLE001 — mismo motivo: no tumbar el proceso al descartar lo roto
                    _warn(f"servidor externo '{cfg.name}': error adicional descartando conexión rota: {close_exc!r}")
                continue
            # Éxito: el stack por-servidor pasa a vivir dentro del stack
            # del pool (se cierra junto con todo lo demás en aclose()).
            await self._stack.enter_async_context(server_stack)
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
