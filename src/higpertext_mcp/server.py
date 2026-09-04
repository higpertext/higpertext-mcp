"""Entrypoint del servidor MCP: registra una tool por cada capability permitida.

Usa `mcp.server.lowlevel.Server`, no `mcp.server.fastmcp.FastMCP` — FastMCP deriva
el inputSchema de los type hints de una función Python fija (`add_tool(fn, ...)`),
lo cual no sirve acá: el schema de cada tool viene de un JSON externo (`schema.py`)
resuelto en runtime, distinto por capability y por perfil activo. El API de bajo
nivel (`list_tools`/`call_tool` como handlers explícitos) es el que soporta eso.
"""

from __future__ import annotations

import asyncio
import json
import sys

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from higpertext_mcp import (
    annotations,
    adapter_renderer,
    discovery,
    dispatch,
    external,
    hook_renderer,
    project_config,
    profile_client,
    resources,
    schema,
)

SERVER_NAME = "higpertext-mcp"
CONFIGURE_TOOL_NAME = "higpertext-configure-project"
CODEX_RULES_TOOL_NAME = "higpertext-generate-codex-rules"
RENDER_ADAPTERS_TOOL_NAME = "higpertext-render-adapters"

_CONFIGURE_TOOL = types.Tool(
    name=CONFIGURE_TOOL_NAME,
    description=(
        "Crea la configuración mínima de higpertext en el proyecto actual: "
        ".higpertext/config/environment.json, mcp_external.json y .mcp.json. "
        "No sobrescribe una configuración existente."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "Nombre de un perfil ya registrado en higpertext-server-profile.",
            }
        },
        "required": ["profile"],
        "additionalProperties": False,
    },
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True),
)
_CODEX_RULES_TOOL = types.Tool(
    name=CODEX_RULES_TOOL_NAME,
    description="Genera o actualiza la sección de reglas del perfil activo en AGENTS.md para Codex.",
    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True),
)
_RENDER_ADAPTERS_TOOL = types.Tool(
    name=RENDER_ADAPTERS_TOOL_NAME,
    description="Genera los archivos nativos de Codex, Claude, Gemini, Copilot, Antigravity y OpenCode desde el perfil activo.",
    inputSchema={"type": "object", "properties": {"assistants": {"type": "array", "items": {"type": "string", "enum": list(adapter_renderer.SUPPORTED)}, "description": "Adapters a renderizar; vacío significa todos."}}, "additionalProperties": False},
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True),
)


async def _load_tools() -> dict[str, schema.ToolSpec]:
    """Perfil activo ∩ catálogo del profile server → specs armadas desde esos Capability.

    Fail-closed: si el profile server no responde, `allowed_capabilities` ya
    devuelve [] (ver discovery.py).
    """
    root = discovery.resolve_project_root()
    tools: dict[str, schema.ToolSpec] = {}
    for capability in await discovery.allowed_capabilities(root):
        tools[capability.id] = schema.tool_spec_from_capability(capability)
    return tools


def _tool_annotations(capability_id: str) -> types.ToolAnnotations:
    hints = annotations.hints_for(capability_id)
    return types.ToolAnnotations(
        readOnlyHint=hints.read_only,
        destructiveHint=hints.destructive,
        idempotentHint=hints.idempotent,
    )


def _mcp_tool_name(capability_id: str) -> str:
    """Sanea un capability_id ("common.grep-search") a un nombre de tool MCP válido.

    Varios clientes (VS Code entre ellos) validan `Tool.name` contra
    `^[a-z0-9_-]+$` y descartan silenciosamente cualquier tool que no matchee
    — un id con "." (la convención real de higpertext-cli) invalida el 100%
    del catálogo. capability_id sigue siendo la clave interna para dispatch;
    esto solo afecta el nombre expuesto al protocolo.
    """
    return capability_id.replace(".", "-")


def _to_mcp_tool(capability_id: str, spec: schema.ToolSpec) -> types.Tool:
    return types.Tool(
        name=_mcp_tool_name(capability_id),
        description=spec.description,
        inputSchema=spec.input_schema,
        annotations=_tool_annotations(capability_id),
    )


def build_server(pool: external.ExternalServerPool | None = None) -> Server:
    server = Server(SERVER_NAME)
    state: dict[str, dict[str, schema.ToolSpec]] = {"tools": {}}
    ext_pool = pool if pool is not None else external.ExternalServerPool([])

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        # Siempre recalculado: si el perfil activo cambió a mitad de sesión,
        # el cliente ve el set correcto apenas vuelve a pedir la lista.
        state["tools"] = await _load_tools()
        state["name_to_id"] = {_mcp_tool_name(cap_id): cap_id for cap_id in state["tools"]}
        local = [_to_mcp_tool(cap_id, spec) for cap_id, spec in state["tools"].items()]
        return [_CONFIGURE_TOOL, _CODEX_RULES_TOOL, _RENDER_ADAPTERS_TOOL, *local, *(await ext_pool.list_tools_merged())]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
        if name == RENDER_ADAPTERS_TOOL_NAME:
            try:
                root = discovery.resolve_project_root()
                profile = discovery.active_profile(root) or ""
                profile_data, caps, rules = await profile_client.profile_context(profile)
                selected = arguments.get("assistants", []) if isinstance(arguments, dict) else []
                data = adapter_renderer.render(root, selected, profile_data, caps, rules)
                data["hooks"] = await hook_renderer.render(root, profile, data["assistants"])
                summary = f"Configuración renderizada para: {', '.join(data['assistants'])}."
                return types.CallToolResult(content=[types.TextContent(type="text", text=summary)], structuredContent={"ok": True, "summary": summary, "data": data})
            except Exception as exc:  # noqa: BLE001
                message = f"No se pudieron renderizar los adapters: {exc}"
                return types.CallToolResult(content=[types.TextContent(type="text", text=message)], isError=True, structuredContent={"ok": False, "summary": message, "data": {}})
        if name == CODEX_RULES_TOOL_NAME:
            try:
                root = discovery.resolve_project_root()
                profile = discovery.active_profile(root)
                profile_data, capabilities, rules = await profile_client.profile_context(profile or "")
                path = project_config.write_codex_rules(root, profile_data, capabilities, rules)
                summary = f"Reglas de Codex generadas en {path}."
                return types.CallToolResult(content=[types.TextContent(type="text", text=summary)], structuredContent={"ok": True, "summary": summary, "data": {"path": path, "rules": len(rules)}})
            except Exception as exc:  # noqa: BLE001
                message = f"No se pudieron generar las reglas de Codex: {exc}"
                return types.CallToolResult(content=[types.TextContent(type="text", text=message)], isError=True, structuredContent={"ok": False, "summary": message, "data": {}})
        if name == CONFIGURE_TOOL_NAME:
            try:
                profile = arguments.get("profile") if isinstance(arguments, dict) else None
                changes = project_config.create_project_configuration(
                    discovery.resolve_project_root(), profile
                )
                summary = "Configuración de higpertext generada."
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=summary)],
                    structuredContent={"ok": True, "summary": summary, "data": changes},
                )
            except (TypeError, ValueError, OSError) as exc:
                message = f"No se pudo generar la configuración: {exc}"
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=message)],
                    isError=True,
                    structuredContent={"ok": False, "summary": message, "data": {}},
                )
        if "name_to_id" not in state:
            # Un cliente puede llamar call_tool() sin haber pedido list_tools()
            # antes (o en tests, que hablan el server directo) — cargar acá
            # evita depender de ese orden, mismo comportamiento que cuando
            # _load_tools() se computaba una vez de forma síncrona al construir
            # el server.
            state["tools"] = await _load_tools()
            state["name_to_id"] = {_mcp_tool_name(cap_id): cap_id for cap_id in state["tools"]}
        tools = state["tools"]
        capability_id = state.get("name_to_id", {}).get(name)
        if capability_id is None:
            if ext_pool.has_tool(name):
                return await ext_pool.call_tool(name, arguments)
            message = f"Unknown tool: {name}"
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=message)],
                isError=True,
                structuredContent={
                    "ok": False,
                    "summary": message,
                    "data": {},
                    "artifacts": [],
                    "warnings": [],
                    "error": message,
                },
            )
        result = await dispatch.call_capability(capability_id, arguments, tools[capability_id].raw)
        await _notify_if_tools_changed(server, state)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=result.summary)],
            isError=not result.ok,
            structuredContent=result.to_dict(),
        )

    @server.list_resources()
    async def list_resources() -> list[types.Resource]:
        return [
            types.Resource(
                uri=resources.USAGE_URI,
                name="Uso de tokens/costo de la sesión",
                description=(
                    "Telemetría real acumulada por el motor higpertext "
                    "(.higpertext/state/telemetry.jsonl), agregada por tool."
                ),
                mimeType="application/json",
            ),
            types.Resource(
                uri=resources.MEMORY_URI,
                name="Memoria de ejecución del proyecto",
                description=(
                    "Historial de ejecuciones de capability registrado en Redis "
                    "(reemplaza el antiguo .memory/journal.json local)."
                ),
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri) -> str:
        root = discovery.resolve_project_root()
        if str(uri) == resources.USAGE_URI:
            return json.dumps(resources.summarize_usage(root), ensure_ascii=False, indent=2)
        if str(uri) == resources.MEMORY_URI:
            data = await resources.read_memory(root)
            return json.dumps(data, ensure_ascii=False, indent=2)
        raise ValueError(f"resource desconocido: {uri}")

    return server


async def _notify_if_tools_changed(
    server: Server, state: dict[str, dict[str, schema.ToolSpec]]
) -> None:
    """Si el perfil activo cambió desde el último list_tools, avisa al cliente.

    No recomputa `state["tools"]` acá — list_tools() sigue siendo la única
    fuente de verdad de lo que el cliente ve; esto solo le dice "volvé a
    preguntar", evitando que quede desactualizado hasta el próximo reinicio.
    """
    root = discovery.resolve_project_root()
    current_ids = {c.id for c in await discovery.allowed_capabilities(root)}
    if current_ids == set(state["tools"].keys()):
        return
    try:
        await server.request_context.session.send_tool_list_changed()
    except LookupError:
        pass


async def _amain() -> None:
    root = discovery.resolve_project_root()
    configs = external.load_external_servers(root)
    async with external.ExternalServerPool(configs) as pool:
        server = build_server(pool)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    run()
