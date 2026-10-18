"""Tool interna ``higpertext-dashboard``: dashboards de agentes desde el JSON.

Permite a un agente consultar el esquema v2, partir de una plantilla, validar, listar,
leer, exportar, importar (crear o actualizar por ``uid``), ver y restaurar versiones,
borrar y ejecutar consultas de la fuente de datos ``agent``. No es una capability de la
DB: se lista siempre, como ``higpertext-roadmap-board``, y se filtra por los scopes del
PAT (ver ``token_permissions``). Habla con rules-api a través de ``dashboard_client``,
actuando en nombre del usuario del PAT validado.
"""

from __future__ import annotations

import json
from typing import Any

import jsonschema

from higpertext_mcp import dashboard_client
from higpertext_mcp.dashboard_client import (
    DashboardApiError,
    DashboardClient,
    DashboardClientError,
    DashboardUnavailable,
)

TOOL_NAME = "higpertext-dashboard"

READ_ACTIONS = ("schema", "templates", "template", "validate", "list", "get", "export", "versions", "version_get")
WRITE_ACTIONS = ("import", "restore", "delete")
QUERY_ACTIONS = ("query",)
ACTIONS = (*READ_ACTIONS, *WRITE_ACTIONS, *QUERY_ACTIONS)

MAX_DATA_BYTES = 65536
LIST_DEFAULT_LIMIT = 50

DESCRIPTION = (
    "Dashboards de agentes definidos por JSON (esquema v2, estilo Grafana): consulta el esquema "
    "(schema) y las plantillas agent-ops, capabilities, governance y flows (templates, template), "
    "valida un JSON sin guardarlo (validate), lista, lee y exporta dashboards (list, get, export), "
    "crea o actualiza por uid (import; idempotente), ve y restaura versiones (versions, version_get, "
    "restore), borra con confirm (delete) y ejecuta consultas de datos de la fuente agent o PromQL "
    "(query: sesiones, auditoría, workflows, boards, herramientas y comandos Bash propios). Actúa "
    "como el usuario de tu PAT: ves y editas solo lo que ese usuario puede. Requiere un PAT validado."
)

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": list(ACTIONS)},
        "id": {"type": "string", "description": "Id del dashboard (get, export, versions, version_get, restore, delete)."},
        "name": {"type": "string", "description": "Nombre de la plantilla (template): agent-ops, capabilities, governance o flows."},
        "settings": {"type": "object", "description": "Configuración JSON del dashboard, v2 con schemaVersion: 2 (validate, import)."},
        "title": {"type": "string", "description": "Título del dashboard (import)."},
        "description": {"type": "string", "description": "Descripción del dashboard (import)."},
        "provisioned": {"type": "boolean", "description": "import: marca el dashboard como gestionado como código; solo import lo actualiza."},
        "scope": {"type": "string", "enum": ["personal", "shared"], "description": "Filtro de list."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": f"list: máximo de dashboards (por defecto {LIST_DEFAULT_LIMIT})."},
        "include_settings": {"type": "boolean", "description": "list: incluir los settings de cada dashboard (por defecto no)."},
        "format": {"type": "string", "enum": ["v1", "v2"], "description": "get: formato de settings (por defecto v2; un v1 se migra al leer)."},
        "version": {"type": "integer", "minimum": 1, "description": "Número de versión (version_get, restore)."},
        "expected_version": {"type": "integer", "minimum": 1, "description": "restore: versión actual esperada; si cambió, responde 409."},
        "confirm": {"type": "boolean", "description": "delete: debe ser true."},
        "project_id": {"type": "string", "description": "query: proyecto a consultar (obligatorio con targets agent o variable_queries)."},
        "targets": {"type": "array", "maxItems": 20, "items": {"type": "object"}, "description": "query: targets {refId, datasource: agent|prometheus, query | expr, hide}."},
        "time": {"type": "object", "properties": {"from": {"type": "string"}, "to": {"type": "string"}}, "additionalProperties": False},
        "variables": {"type": "object", "description": "query: variables $name (string o lista de strings)."},
        "max_data_points": {"type": "integer", "minimum": 1, "maximum": 1000},
        "variable_queries": {"type": "array", "items": {"type": "object"}, "description": "query: variables de tipo query {name, query: {entity, values}}."},
    },
    "required": ["action"],
    "additionalProperties": False,
}

_REQUIRED = {
    "template": ("name",),
    "validate": ("settings",),
    "get": ("id",),
    "export": ("id",),
    "versions": ("id",),
    "version_get": ("id", "version"),
    "restore": ("id", "version"),
    "delete": ("id",),
    "import": ("title", "settings"),
    "query": ("project_id",),
}


def _result(ok: bool, summary: str, data: dict[str, Any] | None = None, *, warnings: list[str] | None = None,
            error: str | None = None) -> dict[str, Any]:
    """Contrato de resultado uniforme: {ok, summary, data, artifacts, warnings, error}."""
    return {"ok": ok, "summary": summary, "data": data or {}, "artifacts": [], "warnings": warnings or [], "error": error}


def _failure(message: str, **data: Any) -> dict[str, Any]:
    return _result(False, message, data, error=message)


def _bounded(data: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    """Una salida enorme no debe llenar el contexto del agente: se reemplaza por un aviso."""
    size = len(json.dumps(data, ensure_ascii=False))
    if size <= MAX_DATA_BYTES:
        return data
    warnings.append(
        f"La respuesta ocupa {size} bytes y supera el tope de {MAX_DATA_BYTES}; se omitió. "
        "Usá una acción más específica (por ejemplo list sin include_settings, o export del dashboard)."
    )
    return {"truncated": True, "bytes": size, "keys": sorted(data)}


def _without_settings(dashboard: Any) -> Any:
    if isinstance(dashboard, dict):
        return {key: value for key, value in dashboard.items() if key != "settings"}
    return dashboard


async def run(arguments: dict[str, Any], token: Any) -> dict[str, Any]:
    """Ejecuta una acción. ``token`` es el ApiTokenContext del PAT validado (None en stdio)."""
    user_id = getattr(token, "user_id", "") if token is not None else ""
    if not user_id:
        return _failure(
            "higpertext-dashboard requiere un PAT validado: actúa en nombre del usuario del token y "
            "no tiene identidad en stdio sin token. Conectate por HTTP con un token de API."
        )
    try:
        jsonschema.validate(instance=arguments, schema=INPUT_SCHEMA)
    except jsonschema.ValidationError as exc:
        return _failure(f"Argumentos inválidos para higpertext-dashboard: {exc.message}")
    action = arguments["action"]
    missing = [field for field in _REQUIRED.get(action, ()) if arguments.get(field) in (None, "")]
    if missing:
        return _failure(f"La acción '{action}' requiere: {', '.join(missing)}.")
    if action == "delete" and arguments.get("confirm") is not True:
        return _failure("delete es destructivo: pasá confirm=true para borrar el dashboard.")

    client = DashboardClient()
    warnings: list[str] = []
    try:
        data, summary = await _dispatch(client, user_id, action, arguments, warnings)
    except DashboardApiError as exc:
        extra = {"status": exc.status, "code": exc.code}
        if "currentVersion" in exc.payload:
            extra["currentVersion"] = exc.payload["currentVersion"]
        return _failure(f"rules-api respondió {exc.status} ({exc.code}): {exc.message}", **extra)
    except DashboardUnavailable as exc:
        return _failure(f"rules-api no está disponible ({exc.code}): {exc.message}", code=exc.code)
    except DashboardClientError as exc:
        return _failure(f"Argumento inválido: {exc}")
    return _result(True, summary, _bounded(data, warnings), warnings=warnings)


async def _dispatch(client: DashboardClient, user_id: str, action: str, args: dict[str, Any],
                    warnings: list[str]) -> tuple[dict[str, Any], str]:
    def call(method: str, *segments: str | int, **kwargs: Any):
        return client.request(method, *segments, on_behalf_of=user_id, **kwargs)

    if action == "schema":
        schema = await call("GET", "schema")
        return {"schema": schema}, "Esquema JSON v2 de los dashboards."
    if action == "templates":
        templates = await call("GET", "templates")
        return {"templates": templates}, f"{len(templates)} plantilla(s) disponibles."
    if action == "template":
        template = await call("GET", "templates", args["name"])
        return {"name": args["name"], **template}, f"Plantilla '{args['name']}': {template.get('title', '')}."
    if action == "validate":
        result = await call("POST", "validate", body={"settings": args["settings"]})
        return result, f"Settings válidos (esquema v{result.get('schemaVersion')})."
    if action == "list":
        query = {"scope": args["scope"]} if args.get("scope") else None
        items = await call("GET", query=query) or []
        limit = args.get("limit", LIST_DEFAULT_LIMIT)
        shown = items[:limit]
        if not args.get("include_settings"):
            shown = [_without_settings(item) for item in shown]
        truncated = len(items) > len(shown)
        if truncated:
            warnings.append(f"Hay {len(items)} dashboards; se muestran {len(shown)}. Subí limit (máx. 100) o filtrá con scope.")
        keep = ("id", "title", "description", "scope", "accessRole", "version", "provisioned", "updatedAt", "settings")
        shown = [{key: item[key] for key in keep if key in item} for item in shown]
        return {"dashboards": shown, "total": len(items), "truncated": truncated}, f"{len(shown)} de {len(items)} dashboard(s)."
    if action == "get":
        dashboard = await call("GET", args["id"], query={"format": args.get("format", "v2")})
        return {"dashboard": dashboard}, f"Dashboard '{dashboard.get('title', args['id'])}' (versión {dashboard.get('version')})."
    if action == "export":
        document = await call("GET", args["id"], "export")
        return {"export": document}, f"Dashboard '{args['id']}' exportado (JSON portable v2)."
    if action == "import":
        body = {"title": args["title"], "description": args.get("description", ""), "settings": args["settings"],
                "provisioned": args.get("provisioned", False)}
        result = await call("POST", "import", body=body)
        dashboard = _without_settings(result.get("dashboard"))
        return {"action": result.get("action"), "dashboard": dashboard}, (
            f"Import {result.get('action')}: dashboard '{(dashboard or {}).get('title', '')}' (versión {(dashboard or {}).get('version')})."
        )
    if action == "versions":
        versions = await call("GET", args["id"], "versions")
        return {"versions": versions}, f"{len(versions)} versión(es) del dashboard '{args['id']}'."
    if action == "version_get":
        snapshot = await call("GET", args["id"], "versions", args["version"])
        return {"version_snapshot": snapshot}, f"Versión {args['version']} del dashboard '{args['id']}'."
    if action == "restore":
        body = {"version": args["expected_version"]} if args.get("expected_version") else None
        dashboard = await call("POST", args["id"], "versions", args["version"], "restore", body=body)
        return {"dashboard": dashboard}, f"Versión {args['version']} restaurada como versión {dashboard.get('version')}."
    if action == "delete":
        await call("DELETE", args["id"])
        return {"deleted": True, "id": args["id"]}, f"Dashboard '{args['id']}' borrado."
    # query
    body: dict[str, Any] = {"projectId": args["project_id"], "targets": args.get("targets", [])}
    for source, target in (("time", "time"), ("variables", "variables"), ("max_data_points", "maxDataPoints"),
                           ("variable_queries", "variableQueries")):
        if source in args:
            body[target] = args[source]
    result = await call("POST", "query", body=body)
    results = result.get("results", {})
    failed = sum(1 for item in results.values() if isinstance(item, dict) and item.get("error"))
    summary = f"{len(results)} target(s) consultados"
    if failed:
        summary += f", {failed} con error"
    return result, summary + "."


__all__ = ["TOOL_NAME", "ACTIONS", "READ_ACTIONS", "WRITE_ACTIONS", "QUERY_ACTIONS", "INPUT_SCHEMA", "DESCRIPTION", "run", "dashboard_client"]
