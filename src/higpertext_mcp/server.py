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

import jsonschema
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from higpertext_mcp import (
    annotations,
    adapter_renderer,
    agent_renderer,
    discovery,
    dispatch,
    external,
    hook_renderer,
    project_config,
    profile_client,
    resources,
    schema,
    skill_renderer,
)

SERVER_NAME = "higpertext-mcp"
CONFIGURE_TOOL_NAME = "higpertext-configure-project"
RENDER_ADAPTERS_TOOL_NAME = "higpertext-render-adapters"
GOVERNANCE_RULE_TOOL_NAME = "higpertext-governance-rule"
PROFILE_TOOL_NAME = "higpertext-profile"
CAPABILITY_TOOL_NAME = "higpertext-capability"
HOOK_TOOL_NAME = "higpertext-hook-admin"
SKILL_TOOL_NAME = "higpertext-skill"
AGENT_TOOL_NAME = "higpertext-agent"
GOVERNANCE_EXCEPTION_TOOL_NAME = "higpertext-governance-exception"

_CONFIGURE_TOOL = types.Tool(
    name=CONFIGURE_TOOL_NAME,
    description=(
        "Crea la configuración mínima de higpertext en un proyecto seleccionado: "
        ".higpertext/config/environment.json, mcp_external.json y .mcp.json. "
        "No sobrescribe una configuración existente. `profile` es obligatorio. "
        "`project_id` y `root_path` son opcionales: si se omiten, usa el proyecto "
        "seleccionado por HIGPERTEXT_PROJECT_ROOT; en un Project multi-ruta, usa "
        "`root_path` para elegir explícitamente cada checkout."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "profile": {
                "type": "string",
                "description": "Nombre de un perfil ya registrado en higpertext-server-profile.",
            },
            "project_id": {
                "type": "string",
                "description": "ID de un proyecto registrado en ProjectService.",
            },
            "root_path": {
                "type": "string",
                "description": "Una ruta registrada del proyecto destino.",
            },
        },
        "required": ["profile"],
        "additionalProperties": False,
    },
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True),
)
_RENDER_ADAPTERS_TOOL = types.Tool(
    name=RENDER_ADAPTERS_TOOL_NAME,
    description=(
        "Genera los archivos nativos desde el perfil activo del proyecto seleccionado. "
        "Requiere exactamente uno de `project_id` o `root_path`; `assistants` solo "
        "filtra los adaptadores a renderizar y no identifica el proyecto. "
        "Si `assistants` se omite o es vacío, renderiza todos los adaptadores."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "project_id": {"type": "string", "description": "ID de un proyecto registrado en ProjectService."},
            "root_path": {"type": "string", "description": "Una ruta registrada del proyecto destino."},
            "assistants": {"type": "array", "items": {"type": "string", "enum": list(adapter_renderer.SUPPORTED)}, "description": "Adapters a renderizar; vacío significa todos."},
        },
        "oneOf": [{"required": ["project_id"]}, {"required": ["root_path"]}],
        "additionalProperties": False,
    },
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True),
)
_GOVERNANCE_RULE_TOOL = types.Tool(
    name=GOVERNANCE_RULE_TOOL_NAME,
    description=(
        "Administra reglas de gobernanza (GovernanceService): crear, listar o borrar. "
        "Si mandás `pattern`, la regla ADEMÁS aplica en runtime — hook_bash_guard "
        "(ver higpertext-mcp/hooks-src) evalúa `pattern` como regex contra cada comando "
        "Bash y bloquea/advierte según `severity`; sin `pattern` es una regla de "
        "gobernanza pura (solo aparece en .claude/rules/<perfil>.md, no intercepta nada). "
        "Tras crear/borrar, corré higpertext-render-adapters para reflejar el cambio en "
        "los archivos de reglas de cada asistente."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "list", "delete"]},
            "id": {"type": "string", "description": "id natural de la regla, ej. 'sec-001' (create/delete)"},
            "description": {"type": "string", "description": "requerido en create"},
            "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
            "scopes": {"type": "array", "items": {"type": "string", "enum": ["COMMIT", "PR", "DEPLOY", "ANY"]}},
            "source": {"type": "string", "description": "'global' o nombre de perfil (default 'global')"},
            "capability": {"type": "string", "description": "id de Capability que valida la regla automáticamente (opcional)"},
            "automated": {"type": "boolean"},
            "numeric_threshold": {"type": "number"},
            "pattern": {"type": "string", "description": "regex opcional (create) — si está presente, hook_bash_guard la evalúa contra comandos Bash en runtime"},
            "scope_filter": {"type": "string", "enum": ["COMMIT", "PR", "DEPLOY", "ANY"], "description": "solo para action=list: filtra por scope"},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False),
)
_HOOK_TOOL = types.Tool(
    name=HOOK_TOOL_NAME,
    description=(
        "Administra el backend de Hooks nativos (HookService) — 100% en la base de "
        "datos del profile server, sin archivos físicos en ningún checkout: crear, "
        "consultar, listar, borrar un hook, y leer/reemplazar el bundle de dependencias "
        "compartidas (hook_utils.py, hook_io.py, _rules/*) que todos los hooks importan. "
        "El `command` que termina en .claude/settings.json o .codex/hooks.json es siempre "
        "`higpertext-hook <id>` — ese id resuelve el script en runtime contra esta misma "
        "base. No hay 'update': para editar, borrá y volvé a crear con el mismo id."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "get", "list", "delete", "get_shared_assets", "set_shared_assets"]},
            "id": {"type": "string", "description": "requerido en create/get/delete"},
            "event": {"type": "string", "enum": ["PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop", "PreCompact"], "description": "requerido en create"},
            "matcher": {"type": "string", "description": "ej. 'Bash', 'Write|Edit', vacío = todos los tools"},
            "description": {"type": "string"},
            "timeout": {"type": "integer", "default": 10},
            "enabled": {"type": "boolean", "default": True},
            "assistants": {"type": "array", "items": {"type": "string"}, "description": "vacío = todos"},
            "profiles": {"type": "array", "items": {"type": "string"}, "description": "vacío = todos los perfiles"},
            "capability_id": {"type": "string"},
            "priority": {"type": "integer", "default": 0},
            "source_code": {"type": "string", "description": "contenido del hook en texto plano (requerido en create) — debe definir main() y usar imports relativos a sus siblings (.hook_utils, .hook_io, ._rules.*), ver higpertext-mcp/hooks-src como referencia de contrato"},
            "script": {"type": "string", "description": "etiqueta/metadata opcional del script; no se lee desde disco"},
            "files": {"type": "object", "additionalProperties": {"type": "string"}, "description": "solo para set_shared_assets: filename (puede incluir subdirectorio, ej. '_rules/bash_rules.py') -> contenido en texto plano. Reemplaza el bundle ENTERO, no hace merge."},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False),
)
_GOVERNANCE_EXCEPTION_TOOL = types.Tool(
    name=GOVERNANCE_EXCEPTION_TOOL_NAME,
    description=(
        "Aprueba, lista o revoca excepciones puntuales a una regla de gobernanza "
        "(GovernanceService.CreateException/ListExceptions/DeleteException) — ej. "
        "mientras se resuelve una deuda técnica, sin tocar la regla en sí."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "list", "delete"]},
            "id": {"type": "string", "description": "requerido en delete"},
            "rule_id": {"type": "string", "description": "requerido en create — id de la GovernanceRule exceptuada"},
            "reason": {"type": "string", "description": "requerido en create"},
            "approver": {"type": "string", "description": "requerido en create"},
            "profile": {"type": "string", "description": "perfil al que aplica la excepción; vacío = todos"},
            "expires": {"type": "string", "description": "fecha YYYY-MM-DD; ausente = sin expiración"},
            "active_only": {"type": "boolean", "description": "solo para list: excluye expiradas"},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False),
)
_PROFILE_TOOL = types.Tool(
    name=PROFILE_TOOL_NAME,
    description=(
        "Administra Profiles — un Profile ES un agente: nombre, system prompt, y qué "
        "capabilities/hooks/subprofiles/reglas tiene habilitados. Crear/editar/borrar acá. "
        "Tras crear o editar uno, corré higpertext-render-adapters para materializarlo "
        "en el proyecto destino."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "get", "list", "update", "delete"]},
            "id": {"type": "string", "description": "requerido en get/update/delete — acepta el UUID interno o el name/slug"},
            "name": {"type": "string", "description": "slug único, requerido en create"},
            "description": {"type": "string"},
            "system_prompt": {"type": "string"},
            "capabilities": {"type": "array", "items": {"type": "string"}, "description": "ids de Capability habilitadas"},
            "subprofiles": {"type": "array", "items": {"type": "string"}},
            "rules": {"type": "array", "items": {"type": "string"}},
            "hooks_global": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False),
)
_CAPABILITY_TOOL = types.Tool(
    name=CAPABILITY_TOOL_NAME,
    description=(
        "Administra el backend de Capabilities (CapabilityService): crear una capability "
        "nueva (el script que un agente puede invocar), consultarla, listar el catálogo "
        "completo o borrarla. No hay 'update' — para editar, borrá y volvé a crear con el "
        "mismo id. Para que una capability recién creada quede utilizable por un agente, "
        "agregá su id a un Profile (ver higpertext-profile)."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "get", "list", "delete"]},
            "id": {"type": "string", "description": "requerido en create/get/delete, ej. 'custom.my-tool'"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "entrypoint": {"type": "string", "description": "path relativo identificador, ej. 'capabilities/custom/scripts/my_tool.py' (solo metadata, no se lee del disco)"},
            "language": {"type": "string", "default": "python"},
            "version": {"type": "string", "default": "1.0.0"},
            "source_code": {"type": "string", "description": "contenido del script en texto plano (requerido en create)"},
            "extra_files": {"type": "object", "additionalProperties": {"type": "string"}, "description": "helpers hermanos: filename -> contenido en texto plano"},
            "parameters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "required": {"type": "boolean"},
                        "description": {"type": "string"},
                        "default": {"type": "string"},
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
            "requires_pat": {"type": "boolean"},
            "hook_task_id": {"type": "string"},
            "contract": {
                "type": "object",
                "properties": {
                    "rules": {"type": "array", "items": {"type": "string"}},
                    "success_pattern": {"type": "string"},
                    "on_empty": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    },
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False),
)
_SKILL_TOOL = types.Tool(
    name=SKILL_TOOL_NAME,
    description=(
        "Administra el catálogo persistente de documentos SKILL.md (SkillService): "
        "crear, consultar, listar, actualizar o borrar. `content` debe empezar con "
        "un front matter YAML cerrado que declare `name` y `description` idénticos "
        "a los del request — el server lo rechaza si no coincide. `profiles`/"
        "`project_id` vacíos (default) significan skill global, compartida por "
        "todo el sistema (convención: id con prefijo 'common.'); seteá `profiles` "
        "para atarla a uno o más perfiles, o `project_id` para atarla a un único "
        "proyecto puntual (ver higpertext-profile action=list para ids de "
        "proyecto — no hay tool de Project todavía, resolvé por root_path vía "
        "higpertext-render-adapters, que ya llama a ResolveProject internamente). "
        "Tras crear/editar/borrar, corré higpertext-render-adapters para reflejar "
        "el cambio en .claude/skills, .gemini/skills, .agents/skills."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "get", "list", "update", "delete"]},
            "id": {"type": "string", "description": "requerido en create/get/update/delete, clave natural (ej. 'common.build')"},
            "name": {"type": "string", "description": "requerido en create/update — debe coincidir con el `name` del front matter de `content`"},
            "description": {"type": "string", "description": "requerido en create/update — debe coincidir con la `description` del front matter de `content`"},
            "content": {"type": "string", "description": "requerido en create/update — el SKILL.md completo, con front matter YAML"},
            "version": {"type": "string", "default": "1.0.0"},
            "enabled": {"type": "boolean", "default": True},
            "profiles": {"type": "array", "items": {"type": "string"}, "description": "vacío = global; si no, la skill solo es visible para estos perfiles"},
            "profile": {"type": "string", "description": "solo para list: filtra por perfil"},
            "project_id": {"type": "string", "description": "vacío = no atada a un proyecto puntual"},
            "enabled_only": {"type": "boolean", "description": "solo para list: solo skills con enabled=true"},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False),
)
_AGENT_TOOL = types.Tool(
    name=AGENT_TOOL_NAME,
    description="Administra agentes y su materialización en los adaptadores configurados.",
    inputSchema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "get", "list", "update", "delete"]},
            "id": {"type": "string", "description": "requerido en create/get/update/delete, clave natural (ej. 'mcp-test-runner')"},
            "name": {"type": "string", "description": "requerido en create/update — frontmatter `name`, normalmente == id"},
            "description": {"type": "string", "description": "requerido en create/update — frontmatter `description`"},
            "tools": {"type": "array", "items": {"type": "string"}, "description": "frontmatter `tools`; vacío = sin restricción"},
            "model": {"type": "string", "description": "requerido en create/update — frontmatter `model`, ej. 'sonnet'"},
            "prompt": {"type": "string", "description": "requerido en create/update — cuerpo markdown, system prompt del subagente"},
            "permission_mode": {"type": "string", "description": "opcional — frontmatter `permissionMode`"},
            "skills": {"type": "array", "items": {"type": "string"}, "description": "opcional — frontmatter `skills`"},
            "memory": {"type": "string", "description": "opcional — frontmatter `memory`"},
            "background": {"type": "boolean", "description": "opcional — sin setear = omitido del frontmatter"},
            "color": {"type": "string", "description": "opcional — frontmatter `color`"},
            "effort": {"type": "string", "description": "opcional — frontmatter `effort`"},
            "assistants": {"type": "array", "items": {"type": "string", "enum": ["claude", "codex"]}, "description": "adaptadores donde se materializa; vacío = todos"},
            "profiles": {"type": "array", "items": {"type": "string"}, "description": "vacío = global; si no, el agent solo es visible para estos perfiles"},
            "profile": {"type": "string", "description": "solo para list: filtra por perfil"},
            "project_id": {"type": "string", "description": "vacío = no atado a un proyecto puntual"},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
    annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False),
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


def _invalid_arguments_result(name: str, arguments: object, error: jsonschema.ValidationError) -> types.CallToolResult:
    """Devuelve errores de argumentos accionables sin filtrar el mensaje crudo de jsonschema."""
    if name == RENDER_ADAPTERS_TOOL_NAME and error.validator == "oneOf":
        detail = "se requiere exactamente uno de 'project_id' o 'root_path'"
    elif error.validator == "required":
        missing = error.message.removeprefix("'").removesuffix("' is a required property")
        detail = f"'{missing}' es obligatorio"
    else:
        path = ".".join(str(part) for part in error.absolute_path)
        location = f" en '{path}'" if path else ""
        detail = f"{error.message}{location}"
    message = f"Parámetros inválidos para '{name}': {detail}."
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=message)],
        isError=True,
        structuredContent={
            "ok": False,
            "summary": message,
            "data": {},
            "error": {
                "code": "invalid_arguments",
                "message": message,
                "arguments": arguments if isinstance(arguments, dict) else {},
            },
        },
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
        return [_CONFIGURE_TOOL, _RENDER_ADAPTERS_TOOL, _GOVERNANCE_RULE_TOOL, _GOVERNANCE_EXCEPTION_TOOL, _PROFILE_TOOL, _CAPABILITY_TOOL, _HOOK_TOOL, _SKILL_TOOL, _AGENT_TOOL, *local, *(await ext_pool.list_tools_merged())]

    # La validación de entrada se hace acá para poder devolver un CallToolResult
    # útil al cliente. La validación automática del SDK corta antes del handler y
    # expone el mensaje crudo de jsonschema (por ejemplo, "no es válido bajo
    # ninguno de los schemas"), que no le indica al modelo cómo corregirse.
    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
        if "name_to_id" not in state:
            state["tools"] = await _load_tools()
            state["name_to_id"] = {_mcp_tool_name(cap_id): cap_id for cap_id in state["tools"]}

        local_tools = {
            tool.name: tool
            for tool in (
                _CONFIGURE_TOOL,
                _RENDER_ADAPTERS_TOOL,
                _GOVERNANCE_RULE_TOOL,
                _GOVERNANCE_EXCEPTION_TOOL,
                _PROFILE_TOOL,
                _CAPABILITY_TOOL,
                _HOOK_TOOL,
                _SKILL_TOOL,
                _AGENT_TOOL,
            )
        }
        capability_id = state["name_to_id"].get(name)
        if capability_id is not None:
            local_tools[name] = _to_mcp_tool(capability_id, state["tools"][capability_id])
        tool = local_tools.get(name)
        if tool is not None:
            try:
                jsonschema.validate(instance=arguments or {}, schema=tool.inputSchema)
            except jsonschema.ValidationError as exc:
                return _invalid_arguments_result(name, arguments, exc)

        if name == RENDER_ADAPTERS_TOOL_NAME:
            try:
                args = arguments if isinstance(arguments, dict) else {}
                root, _project = await discovery.resolve_registered_project(
                    root_path=args.get("root_path", ""),
                    project_id=args.get("project_id", ""),
                )
                profile = discovery.active_profile(root) or ""
                profile_data, caps, rules = await profile_client.profile_context(profile)
                selected = args.get("assistants", [])
                data = adapter_renderer.render(root, selected, profile_data, caps, rules)
                data["hooks"] = await hook_renderer.render(root, profile, data["assistants"])
                data["skills"] = await skill_renderer.render(root, profile, data["assistants"])
                data["agents"] = await agent_renderer.render(root, profile, data["assistants"])
                summary = f"Configuración renderizada para: {', '.join(data['assistants'])}."
                return types.CallToolResult(content=[types.TextContent(type="text", text=summary)], structuredContent={"ok": True, "summary": summary, "data": data})
            except Exception as exc:  # noqa: BLE001
                message = f"No se pudieron renderizar los adapters: {exc}"
                return types.CallToolResult(content=[types.TextContent(type="text", text=message)], isError=True, structuredContent={"ok": False, "summary": message, "data": {}})
        if name == GOVERNANCE_RULE_TOOL_NAME:
            args = arguments if isinstance(arguments, dict) else {}
            action = args.get("action")
            try:
                if action == "create":
                    rule = await profile_client.create_governance_rule(
                        id=args["id"],
                        description=args.get("description", ""),
                        severity=args.get("severity", "MEDIUM"),
                        scopes=args.get("scopes") or ["ANY"],
                        source=args.get("source", "global"),
                        capability=args.get("capability", ""),
                        automated=bool(args.get("automated", False)),
                        numeric_threshold=args.get("numeric_threshold"),
                        pattern=args.get("pattern", ""),
                    )
                    summary = f"Regla '{rule.id}' creada ({profile_client.profile_pb2.Severity.Name(rule.severity)})."
                    data = {"id": rule.id, "description": rule.description, "severity": profile_client.profile_pb2.Severity.Name(rule.severity), "scopes": [profile_client.profile_pb2.Scope.Name(s) for s in rule.scopes], "source": rule.source, "pattern": rule.pattern}
                elif action == "list":
                    rules = await profile_client.list_governance_rules(args.get("scope_filter", ""))
                    summary = f"{len(rules)} regla(s) de gobernanza."
                    data = {"rules": [
                        {
                            "id": r.id,
                            "description": r.description,
                            "severity": profile_client.profile_pb2.Severity.Name(r.severity),
                            "scopes": [profile_client.profile_pb2.Scope.Name(s) for s in r.scopes],
                            "source": r.source,
                            "capability": r.capability,
                            "pattern": r.pattern,
                        }
                        for r in rules
                    ]}
                elif action == "delete":
                    await profile_client.delete_governance_rule(args["id"])
                    summary = f"Regla '{args['id']}' borrada."
                    data = {"id": args["id"]}
                else:
                    raise ValueError(f"action inválida: {action!r} (usar create|list|delete)")
                return types.CallToolResult(content=[types.TextContent(type="text", text=summary)], structuredContent={"ok": True, "summary": summary, "data": data})
            except Exception as exc:  # noqa: BLE001
                message = f"No se pudo administrar la regla de gobernanza: {exc}"
                return types.CallToolResult(content=[types.TextContent(type="text", text=message)], isError=True, structuredContent={"ok": False, "summary": message, "data": {}})
        if name == PROFILE_TOOL_NAME:
            args = arguments if isinstance(arguments, dict) else {}
            action = args.get("action")
            try:
                if action == "create":
                    data = await profile_client.create_profile(
                        name=args["name"], description=args.get("description", ""),
                        system_prompt=args.get("system_prompt", ""), capabilities=args.get("capabilities"),
                        subprofiles=args.get("subprofiles"), rules=args.get("rules"), hooks_global=args.get("hooks_global"),
                    )
                    summary = f"Profile '{data['name']}' creado."
                elif action == "get":
                    data = await profile_client.get_profile(args["id"])
                    summary = f"Profile '{data['name']}'."
                elif action == "list":
                    profiles = await profile_client.list_profiles()
                    data = {"profiles": profiles}
                    summary = f"{len(profiles)} profile(s)."
                elif action == "update":
                    data = await profile_client.update_profile(
                        id=args["id"], name=args.get("name", ""), description=args.get("description", ""),
                        system_prompt=args.get("system_prompt", ""), capabilities=args.get("capabilities"),
                        subprofiles=args.get("subprofiles"), rules=args.get("rules"), hooks_global=args.get("hooks_global"),
                    )
                    summary = f"Profile '{data['name']}' actualizado."
                elif action == "delete":
                    await profile_client.delete_profile(args["id"])
                    data = {"id": args["id"]}
                    summary = f"Profile '{args['id']}' borrado."
                else:
                    raise ValueError(f"action inválida: {action!r} (usar create|get|list|update|delete)")
                return types.CallToolResult(content=[types.TextContent(type="text", text=summary)], structuredContent={"ok": True, "summary": summary, "data": data})
            except Exception as exc:  # noqa: BLE001
                message = f"No se pudo administrar el profile: {exc}"
                return types.CallToolResult(content=[types.TextContent(type="text", text=message)], isError=True, structuredContent={"ok": False, "summary": message, "data": {}})
        if name == CAPABILITY_TOOL_NAME:
            args = arguments if isinstance(arguments, dict) else {}
            action = args.get("action")
            try:
                if action == "create":
                    data = await profile_client.create_capability(
                        id=args["id"], entrypoint=args.get("entrypoint", ""), source_code=args.get("source_code", ""),
                        name=args.get("name", ""), description=args.get("description", ""),
                        version=args.get("version", "1.0.0"), language=args.get("language", "python"),
                        parameters=args.get("parameters"), requires_pat=bool(args.get("requires_pat", False)),
                        hook_task_id=args.get("hook_task_id", ""), contract=args.get("contract"),
                        extra_files=args.get("extra_files"),
                    )
                    summary = f"Capability '{data['id']}' creada."
                elif action == "get":
                    data = await profile_client.get_capability(args["id"])
                    summary = f"Capability '{data['id']}'."
                elif action == "list":
                    caps = await profile_client.list_capabilities_raw()
                    data = {"capabilities": caps}
                    summary = f"{len(caps)} capability(ies) en el catálogo."
                elif action == "delete":
                    await profile_client.delete_capability(args["id"])
                    data = {"id": args["id"]}
                    summary = f"Capability '{args['id']}' borrada."
                else:
                    raise ValueError(f"action inválida: {action!r} (usar create|get|list|delete)")
                return types.CallToolResult(content=[types.TextContent(type="text", text=summary)], structuredContent={"ok": True, "summary": summary, "data": data})
            except Exception as exc:  # noqa: BLE001
                message = f"No se pudo administrar la capability: {exc}"
                return types.CallToolResult(content=[types.TextContent(type="text", text=message)], isError=True, structuredContent={"ok": False, "summary": message, "data": {}})
        if name == HOOK_TOOL_NAME:
            args = arguments if isinstance(arguments, dict) else {}
            action = args.get("action")
            try:
                if action == "create":
                    data = await profile_client.create_hook(
                        id=args["id"], event=args["event"], matcher=args.get("matcher", ""),
                        description=args.get("description", ""), timeout=int(args.get("timeout", 10)),
                        enabled=bool(args.get("enabled", True)), assistants=args.get("assistants"),
                        profiles=args.get("profiles"), capability_id=args.get("capability_id", ""),
                        priority=int(args.get("priority", 0)), source_code=args.get("source_code", ""),
                        script=args.get("script", ""),
                    )
                    summary = f"Hook '{data['id']}' creado ({data['event']})."
                elif action == "get":
                    data = await profile_client.get_hook(args["id"])
                    summary = f"Hook '{data['id']}'."
                elif action == "list":
                    hooks = await profile_client.list_hooks_raw()
                    data = {"hooks": hooks}
                    summary = f"{len(hooks)} hook(s) en el catálogo."
                elif action == "delete":
                    await profile_client.delete_hook(args["id"])
                    data = {"id": args["id"]}
                    summary = f"Hook '{args['id']}' borrado."
                elif action == "get_shared_assets":
                    assets = await profile_client.get_shared_hook_assets()
                    data = {"files": assets}
                    summary = f"{len(assets)} archivo(s) en el bundle compartido."
                elif action == "set_shared_assets":
                    assets = await profile_client.set_shared_hook_assets(args.get("files") or {})
                    data = {"files": list(assets.keys())}
                    summary = f"Bundle compartido reemplazado ({len(assets)} archivo(s))."
                else:
                    raise ValueError(f"action inválida: {action!r} (usar create|get|list|delete|get_shared_assets|set_shared_assets)")
                return types.CallToolResult(content=[types.TextContent(type="text", text=summary)], structuredContent={"ok": True, "summary": summary, "data": data})
            except Exception as exc:  # noqa: BLE001
                message = f"No se pudo administrar el hook: {exc}"
                return types.CallToolResult(content=[types.TextContent(type="text", text=message)], isError=True, structuredContent={"ok": False, "summary": message, "data": {}})
        if name == SKILL_TOOL_NAME:
            args = arguments if isinstance(arguments, dict) else {}
            action = args.get("action")
            try:
                if action == "create":
                    data = await profile_client.create_skill(
                        id=args["id"], name=args.get("name", ""), description=args.get("description", ""),
                        content=args.get("content", ""), version=args.get("version", "1.0.0"),
                        enabled=bool(args.get("enabled", True)), profiles=args.get("profiles"),
                        project_id=args.get("project_id", ""),
                    )
                    summary = f"Skill '{data['id']}' creada."
                elif action == "get":
                    data = await profile_client.get_skill(args["id"])
                    summary = f"Skill '{data['id']}'."
                elif action == "list":
                    skills = await profile_client.list_skills(
                        enabled_only=bool(args.get("enabled_only", False)),
                        profile=args.get("profile", ""),
                        project_id=args.get("project_id", ""),
                    )
                    data = {"skills": skills}
                    summary = f"{len(skills)} skill(s) en el catálogo."
                elif action == "update":
                    data = await profile_client.update_skill(
                        id=args["id"], name=args["name"], description=args["description"],
                        content=args["content"], version=args.get("version", "1.0.0"),
                        enabled=bool(args.get("enabled", True)), profiles=args.get("profiles"),
                        project_id=args.get("project_id", ""),
                    )
                    summary = f"Skill '{data['id']}' actualizada."
                elif action == "delete":
                    await profile_client.delete_skill(args["id"])
                    data = {"id": args["id"]}
                    summary = f"Skill '{args['id']}' borrada."
                else:
                    raise ValueError(f"action inválida: {action!r} (usar create|get|list|update|delete)")
                return types.CallToolResult(content=[types.TextContent(type="text", text=summary)], structuredContent={"ok": True, "summary": summary, "data": data})
            except Exception as exc:  # noqa: BLE001
                message = f"No se pudo administrar la skill: {exc}"
                return types.CallToolResult(content=[types.TextContent(type="text", text=message)], isError=True, structuredContent={"ok": False, "summary": message, "data": {}})
        if name == AGENT_TOOL_NAME:
            args = arguments if isinstance(arguments, dict) else {}
            action = args.get("action")
            try:
                if action == "create":
                    data = await profile_client.create_agent(
                        id=args["id"], name=args.get("name", ""), description=args.get("description", ""),
                        tools=args.get("tools"), model=args.get("model", ""), prompt=args.get("prompt", ""),
                        permission_mode=args.get("permission_mode", ""), skills=args.get("skills"),
                        memory=args.get("memory", ""), background=args.get("background"),
                        color=args.get("color", ""), effort=args.get("effort", ""),
                        assistants=args.get("assistants"), profiles=args.get("profiles"),
                        project_id=args.get("project_id", ""),
                    )
                    summary = f"Agent '{data['id']}' creado."
                elif action == "get":
                    data = await profile_client.get_agent(args["id"])
                    summary = f"Agent '{data['id']}'."
                elif action == "list":
                    agents = await profile_client.list_agents(
                        profile=args.get("profile", ""), project_id=args.get("project_id", ""),
                    )
                    data = {"agents": agents}
                    summary = f"{len(agents)} agent(s) en el catálogo."
                elif action == "update":
                    data = await profile_client.update_agent(
                        id=args["id"], name=args["name"], description=args["description"],
                        tools=args.get("tools"), model=args["model"], prompt=args["prompt"],
                        permission_mode=args.get("permission_mode", ""), skills=args.get("skills"),
                        memory=args.get("memory", ""), background=args.get("background"),
                        color=args.get("color", ""), effort=args.get("effort", ""),
                        assistants=args.get("assistants"), profiles=args.get("profiles"),
                        project_id=args.get("project_id", ""),
                    )
                    summary = f"Agent '{data['id']}' actualizado."
                elif action == "delete":
                    await profile_client.delete_agent(args["id"])
                    data = {"id": args["id"]}
                    summary = f"Agent '{args['id']}' borrado."
                else:
                    raise ValueError(f"action inválida: {action!r} (usar create|get|list|update|delete)")
                return types.CallToolResult(content=[types.TextContent(type="text", text=summary)], structuredContent={"ok": True, "summary": summary, "data": data})
            except Exception as exc:  # noqa: BLE001
                message = f"No se pudo administrar el agent: {exc}"
                return types.CallToolResult(content=[types.TextContent(type="text", text=message)], isError=True, structuredContent={"ok": False, "summary": message, "data": {}})
        if name == GOVERNANCE_EXCEPTION_TOOL_NAME:
            args = arguments if isinstance(arguments, dict) else {}
            action = args.get("action")
            try:
                if action == "create":
                    data = await profile_client.create_governance_exception(
                        rule_id=args["rule_id"], reason=args["reason"], approver=args["approver"],
                        profile=args.get("profile", ""), expires=args.get("expires"),
                    )
                    summary = f"Excepción '{data['id']}' creada para la regla '{data['rule_id']}'."
                elif action == "list":
                    exceptions = await profile_client.list_governance_exceptions(
                        profile=args.get("profile", ""), active_only=bool(args.get("active_only", False)),
                    )
                    data = {"exceptions": exceptions}
                    summary = f"{len(exceptions)} excepción(es)."
                elif action == "delete":
                    await profile_client.delete_governance_exception(args["id"])
                    data = {"id": args["id"]}
                    summary = f"Excepción '{args['id']}' borrada."
                else:
                    raise ValueError(f"action inválida: {action!r} (usar create|list|delete)")
                return types.CallToolResult(content=[types.TextContent(type="text", text=summary)], structuredContent={"ok": True, "summary": summary, "data": data})
            except Exception as exc:  # noqa: BLE001
                message = f"No se pudo administrar la excepción de gobernanza: {exc}"
                return types.CallToolResult(content=[types.TextContent(type="text", text=message)], isError=True, structuredContent={"ok": False, "summary": message, "data": {}})
        if name == CONFIGURE_TOOL_NAME:
            try:
                args = arguments if isinstance(arguments, dict) else {}
                profile = args.get("profile")
                if args.get("root_path") or args.get("project_id"):
                    root, _project = await discovery.resolve_registered_project(
                        root_path=args.get("root_path", ""),
                        project_id=args.get("project_id", ""),
                    )
                    selector = "project_id" if args.get("project_id") else "root_path"
                else:
                    root = discovery.resolve_project_root()
                    selector = "HIGPERTEXT_PROJECT_ROOT"
                changes = project_config.create_project_configuration(
                    root, profile
                )
                summary = f"Configuración de higpertext generada en {root}."
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=summary)],
                    structuredContent={
                        "ok": True,
                        "summary": summary,
                        "data": {"root": str(root), "selector": selector, "changes": changes},
                    },
                )
            except RuntimeError as exc:
                message = (
                    "No se pudo seleccionar el proyecto: no hay un proyecto destino "
                    "configurado; indique 'project_id' o 'root_path'."
                )
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=message)],
                    isError=True,
                    structuredContent={
                        "ok": False,
                        "summary": message,
                        "data": {},
                        "error": {"code": "project_not_selected", "message": message},
                    },
                )
            except (TypeError, ValueError, OSError) as exc:
                message = f"No se pudo generar la configuración: {exc}"
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=message)],
                    isError=True,
                    structuredContent={
                        "ok": False,
                        "summary": message,
                        "data": {},
                        "error": {"code": "configuration_error", "message": message},
                    },
                )
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
