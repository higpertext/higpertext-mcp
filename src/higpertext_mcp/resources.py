"""Expone telemetría de uso y memoria de ejecución como MCP resources.

`summarize_usage` es dato de solo lectura que ya existe en disco
(.higpertext/state/telemetry.jsonl, escrito por hook_post_observer.py del
motor) — no tiene sentido envolverlo en una tool cuando el modelo puede
leerlo pasivamente como resource, sin gastar un tool call. `read_memory` es
el mismo criterio aplicado a la memoria de ejecución, que ahora vive en Redis
(`memory.py`) en vez de `.memory/journal.json`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from higpertext_mcp import memory

USAGE_URI = "higpertext://session/usage"
MEMORY_URI = "higpertext://session/memory"

_TELEMETRY_REL_PATH = Path(".higpertext") / "state" / "telemetry.jsonl"


def _read_telemetry_lines(root: Path) -> list[dict]:
    path = root / _TELEMETRY_REL_PATH
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def summarize_usage(root: Path) -> dict:
    """Agrega tokens/costo estimado por tool a partir de la telemetría en disco."""
    entries = _read_telemetry_lines(root)
    by_tool: dict[str, dict[str, float]] = {}
    total_tokens = 0
    total_cost = 0.0
    for entry in entries:
        if entry.get("event") != "tool_call":
            continue
        tool = entry.get("tool", "unknown")
        tokens = entry.get("estimated_tokens", 0) or 0
        cost = entry.get("estimated_cost_usd", 0) or 0
        bucket = by_tool.setdefault(tool, {"tokens": 0, "cost_usd": 0.0, "calls": 0})
        bucket["tokens"] += tokens
        bucket["cost_usd"] += cost
        bucket["calls"] += 1
        total_tokens += tokens
        total_cost += cost
    return {
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "calls": len(entries),
        "by_tool": by_tool,
    }


async def read_memory(root: Path) -> dict[str, Any]:
    """Memoria de ejecución del proyecto (Redis), más reciente primero."""
    entries = await memory.list_memory(root)
    return {"entries": entries}
