"""Expone telemetría real de uso (.higpertext/state/telemetry.jsonl) como MCP resource.

Es dato de solo lectura que ya existe en disco (lo escribe hook_post_observer.py
del motor) — no tiene sentido envolverlo en una tool cuando el modelo puede
leerlo pasivamente como resource, sin gastar un tool call.
"""

from __future__ import annotations

import json
from pathlib import Path

USAGE_URI = "higpertext://session/usage"

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
