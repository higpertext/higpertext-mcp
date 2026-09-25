"""Traduce el `Capability` del profile server (parameters[]) a JSON Schema MCP.

La metadata de cada capability (descripción, parámetros, contrato) ya no se lee
de JSON local en higpertext-cli: viene de `CapabilityService.ListCapabilities`
del profile server (ver `discovery.allowed_capabilities` / `profile_client`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from higpertext_mcp.gen.profile.v1 import profile_pb2


# Algunas capabilities históricas fueron registradas antes de que el contrato
# Proto soportara tipos ricos. Esta tabla mantiene la corrección en un único
# punto, sin borrar/recrear capabilities (lo que podría perder source_code), y
# permite migrarlas gradualmente en el catálogo del profile server.
_COMMON_PARAMETER_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "common.context-assembler": {
        "type": {"type": "string", "enum_values": ["refactor", "feature", "bugfix", "review"]},
    },
    "common.context-budget-report": {
        "operation": {"type": "string", "enum_values": ["read", "search", "skeleton"]},
        "json": {"type": "boolean"},
    },
    "common.diff-impact-analyzer": {
        "files": {"type": "array", "items": {"type": "string"}},
        "format": {"type": "string", "enum_values": ["text", "json"]},
    },
    "common.error-context-locator": {
        "max_context": {"type": "integer"},
        "include_tests": {"type": "boolean"},
        "json": {"type": "boolean"},
    },
    "common.governance-exception": {
        "action": {"type": "string", "enum_values": ["register", "list"]},
    },
    "common.graph-query": {
        "depth": {"type": "integer"},
        "budget": {"type": "integer"},
        "type": {"type": "string", "enum_values": ["class", "function", "method", "variable", "module"]},
        "limit": {"type": "integer"},
        "files_only": {"type": "boolean"},
        "json": {"type": "boolean"},
    },
    "common.graph-rebuild": {"god_threshold": {"type": "integer"}},
    "common.grep-search": {
        "include": {"type": "array", "items": {"type": "string"}},
        "extension": {"type": "array", "items": {"type": "string"}},
        "exclude": {"type": "array", "items": {"type": "string"}},
        "regex": {"type": "boolean"},
        "case_sensitive": {"type": "boolean"},
        "context": {"type": "integer"},
        "before": {"type": "integer"},
        "after": {"type": "integer"},
        "max_results": {"type": "integer"},
        "max_per_file": {"type": "integer"},
        "line_limit": {"type": "integer"},
        "max_file_size_kb": {"type": "integer"},
        "sort": {"type": "string", "enum_values": ["relevance", "path"]},
        "preset": {"type": "string", "enum_values": ["all", "code", "python", "web", "docs", "config"]},
        "include_tests": {"type": "boolean"},
        "source_first": {"type": "boolean"},
        "files_only": {"type": "boolean"},
        "count": {"type": "boolean"},
        "semantic": {"type": "boolean"},
        "json": {"type": "boolean"},
        "absolute_paths": {"type": "boolean"},
        "all": {"type": "boolean"},
    },
    "common.memory-manager": {
        "learned": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "common.quality-resolver": {
        "mode": {"type": "string", "enum_values": ["update", "create"]},
    },
    "common.roadmap-phase-advance": {
        "target": {"type": "string", "enum_values": ["Pending", "Active", "Done"]},
        "position": {"type": "integer"},
    },
    "common.roadmap-phase-create": {
        "priority": {"type": "string", "enum_values": ["LOW", "MEDIUM", "HIGH", "CRITICAL", "PRIORITY_UNSPECIFIED"]},
        "tags": {"type": "array", "items": {"type": "string"}},
        "tasks": {"type": "array", "items": {"type": "string"}},
        "item_type": {"type": "string", "enum_values": ["ROADMAP", "EPIC", "FEATURE", "STORY", "BUG", "ISSUE"]},
    },
    "common.search-router": {
        "intent": {"type": "string", "enum_values": ["error", "feature", "refactor", "docs", "symbol", "general"]},
        "preset": {"type": "string", "enum_values": ["all", "code", "python", "web", "docs", "config"]},
        "json": {"type": "boolean"},
    },
    "common.semantic-diff": {
        "files": {"type": "array", "items": {"type": "string"}},
        "format": {"type": "string", "enum_values": ["text", "json"]},
    },
    "common.semantic-search": {"limit": {"type": "integer"}},
    "common.server-verification-report": {
        "format": {"type": "string", "enum_values": ["text", "json"]},
    },
    "common.skill-resolver": {
        "exclude": {"type": "array", "items": {"type": "string"}},
        "max_skills": {"type": "integer"},
        "json": {"type": "boolean"},
    },
    "common.smart-read": {
        "mode": {"type": "string", "enum_values": ["auto", "skeleton", "range", "symbol", "full", "summary"]},
        "offset": {"type": "integer"},
        "limit": {"type": "integer"},
        "around_line": {"type": "integer"},
        "max_bytes": {"type": "integer"},
        "max_tokens": {"type": "integer"},
        "json": {"type": "boolean"},
    },
    "common.truth-keeper": {
        "action": {"type": "string", "enum_values": ["set", "get", "delete", "list"]},
    },
}


@dataclass
class ToolSpec:
    capability_id: str
    description: str
    input_schema: dict[str, Any]
    raw: dict[str, Any]


def _infer_type(default: Any, declared_type: Any = None) -> str:
    """Infiere el tipo JSON Schema a partir del default string de la capability.

    Todas las capabilities declaran sus defaults como string (formato CLI), pero
    el valor real que representan puede ser bool o int — ver `_parse_bool` en
    grep_search.py, que acepta "True"/"true" indistintamente, así que anunciar
    el tipo real acá no rompe el dispatch in-process (str(True) -> "True" sigue
    siendo válido para el parser de la capability).
    """
    if isinstance(declared_type, str) and declared_type:
        aliases = {
            "bool": "boolean", "boolean": "boolean",
            "int": "integer", "integer": "integer",
            "float": "number", "number": "number",
            "dict": "object", "object": "object",
            "list": "array", "array": "array",
            "str": "string", "string": "string",
        }
        if declared_type.strip().lower() in aliases:
            return aliases[declared_type.strip().lower()]
    if not isinstance(default, str):
        return "string"
    if default.lower() in ("true", "false"):
        return "boolean"
    if re.fullmatch(r"-?\d+", default):
        return "integer"
    return "string"


def _schema_default(default: Any, declared_type: Any = None) -> Any:
    """Convierte el default textual del catálogo al tipo anunciado al cliente."""
    kind = _infer_type(default, declared_type)
    if kind == "boolean" and isinstance(default, str):
        return default.lower() == "true"
    if kind == "integer" and isinstance(default, str):
        try:
            return int(default)
        except ValueError:
            return default
    if kind == "number" and isinstance(default, str):
        try:
            return float(default)
        except ValueError:
            return default
    return default


def _build_input_schema(parameters: list[dict]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in parameters:
        name = param.get("name")
        if not name:
            continue
        default = param.get("default")
        prop: dict[str, Any] = {
            "type": _infer_type(default, param.get("type")) if default is not None else _infer_type(None, param.get("type")),
            "description": param.get("description", ""),
        }
        if param.get("items"):
            prop["items"] = param["items"]
        enum_values = param.get("enum_values") or []
        if enum_values:
            prop["enum"] = list(enum_values)
        # Un valor vacío en un parámetro numérico representa ausencia en el
        # catálogo histórico; no lo publiques como default inválido.
        if default is not None and not (default == "" and prop["type"] != "string"):
            prop["default"] = _schema_default(default, param.get("type"))
        properties[name] = prop
        if param.get("required", False):
            required.append(name)
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _build_description(definition: dict) -> str:
    """Descripción que ve el modelo al elegir la tool.

    No repite los parámetros (ya viajan en `inputSchema` con su propia
    descripción) ni `contract.rules`: esas reglas son la especificación para
    quien implementa el script, no guía para quien lo llama — y duplicarlas
    costaba ~2x tokens por tool en clientes que cargan todo el catálogo.
    `on_empty` sí se conserva: evita que el agente reintente ante un vacío
    legítimo.
    """
    parts = [definition.get("description", "")]
    on_empty = definition.get("contract", {}).get("on_empty")
    if on_empty:
        parts.append(f"Si no hay resultados: {on_empty}")
    return "\n".join(p for p in parts if p)


def _capability_to_raw(cap: profile_pb2.Capability) -> dict[str, Any]:
    """Reconstruye el dict-shape que hoy consumen `normalize_and_validate_params`
    y `ContractValidator` de higpertext-cli (mismas claves que el JSON de
    definición original), a partir del `Capability` del profile server.

    Un parámetro sin default declarado llega como `""` (proto3 no distingue
    "campo vacío" de "campo ausente") — se omite la clave `default` en ese
    caso, igual que cuando el JSON original no la traía.
    """
    overrides = _COMMON_PARAMETER_OVERRIDES.get(cap.id, {})
    parameters = []
    for p in cap.parameters:
        param: dict[str, Any] = {
            "name": p.name,
            "type": p.type,
            "required": p.required,
            "description": p.description,
            "enum_values": list(p.enum_values),
        }
        param.update(overrides.get(p.name, {}))
        if p.default:
            param["default"] = p.default
        parameters.append(param)
    contract: dict[str, Any] = {"rules": list(cap.contract.rules)}
    if cap.contract.success_pattern:
        contract["success_pattern"] = cap.contract.success_pattern
    if cap.contract.on_empty:
        contract["on_empty"] = cap.contract.on_empty
    return {
        "id": cap.id,
        "entrypoint": cap.entrypoint,
        "language": cap.language,
        "parameters": parameters,
        "contract": contract,
        "description": cap.description,
    }


def tool_spec_from_capability(cap: profile_pb2.Capability) -> ToolSpec:
    raw = _capability_to_raw(cap)
    return ToolSpec(
        capability_id=cap.id,
        description=_build_description(raw),
        input_schema=_build_input_schema(raw["parameters"]),
        raw=raw,
    )
