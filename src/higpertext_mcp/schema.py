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


@dataclass
class ToolSpec:
    capability_id: str
    description: str
    input_schema: dict[str, Any]
    raw: dict[str, Any]


def _infer_type(default: Any) -> str:
    """Infiere el tipo JSON Schema a partir del default string de la capability.

    Todas las capabilities declaran sus defaults como string (formato CLI), pero
    el valor real que representan puede ser bool o int — ver `_parse_bool` en
    grep_search.py, que acepta "True"/"true" indistintamente, así que anunciar
    el tipo real acá no rompe el dispatch in-process (str(True) -> "True" sigue
    siendo válido para el parser de la capability).
    """
    if not isinstance(default, str):
        return "string"
    if default.lower() in ("true", "false"):
        return "boolean"
    if re.fullmatch(r"-?\d+", default):
        return "integer"
    return "string"


def _build_input_schema(parameters: list[dict]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in parameters:
        name = param.get("name")
        if not name:
            continue
        default = param.get("default")
        prop: dict[str, Any] = {
            "type": _infer_type(default) if default is not None else "string",
            "description": param.get("description", ""),
        }
        if default is not None:
            prop["default"] = default
        properties[name] = prop
        if param.get("required", False):
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _build_description(definition: dict) -> str:
    parts = [definition.get("description", "")]
    contract = definition.get("contract", {})
    rules = contract.get("rules", [])
    if rules:
        parts.append("Reglas:")
        parts.extend(f"- {rule}" for rule in rules)
    on_empty = contract.get("on_empty")
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
    parameters = []
    for p in cap.parameters:
        param: dict[str, Any] = {
            "name": p.name,
            "required": p.required,
            "description": p.description,
        }
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
