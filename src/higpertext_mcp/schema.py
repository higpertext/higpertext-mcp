"""Traduce el JSON de definición de una capability (parameters[]) a JSON Schema MCP.

Reusa `list_rules.load_capability_meta`, ya presente en higpertext-cli, en vez de
reimplementar el escaneo de `capabilities/<namespace>/**/*.json` — esa función ya
cubre el layout inconsistente entre `common.*` (definitions/) y `git.*`/`security.*`
(json plano en la raíz del namespace).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from higpertext.capabilities.common.scripts.core.governance.list_rules import (
    load_capability_meta,
)


@dataclass
class ToolSpec:
    capability_id: str
    description: str
    input_schema: dict[str, Any]


def _build_input_schema(parameters: list[dict]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in parameters:
        name = param.get("name")
        if not name:
            continue
        prop: dict[str, Any] = {
            "type": "string",
            "description": param.get("description", ""),
        }
        if "default" in param:
            prop["default"] = param["default"]
        properties[name] = prop
        if param.get("required", False):
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _build_description(definition: dict) -> str:
    parts = [definition.get("description", "")]
    rules = definition.get("contract", {}).get("rules", [])
    if rules:
        parts.append("Reglas:")
        parts.extend(f"- {rule}" for rule in rules)
    return "\n".join(p for p in parts if p)


def load_tool_spec(capability_id: str) -> ToolSpec | None:
    definition = load_capability_meta(capability_id)
    if not definition:
        return None
    return ToolSpec(
        capability_id=capability_id,
        description=_build_description(definition),
        input_schema=_build_input_schema(definition.get("parameters", [])),
    )
