"""Expone telemetría de uso y memoria de ejecución como MCP resources.

`summarize_usage` agrega la telemetría que escriben los hooks
`hook_post_observer` (un evento `tool_call` por tool, con `context_tokens`:
lo que el modelo realmente recibió) y `hook_context_usage` (un evento
`context_usage` por turno, con el contexto real leído del transcript). Ambos
escriben en Redis bajo ``higpertext:telemetry:<project_id|sha256(root)[:16]>:<sesión>``
(ver el asset compartido `_telemetry.py`). Es dato de solo lectura: el modelo
lo lee pasivamente como resource, sin gastar un tool call. `read_memory` es
el mismo criterio aplicado a la memoria de ejecución (`memory.py`).
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from higpertext_mcp import discovery, memory
from higpertext_mcp.project_resolution import cached_project_id

USAGE_URI = "higpertext://session/usage"
MEMORY_URI = "higpertext://session/memory"

_TELEMETRY_PREFIX = "higpertext:telemetry"
_TOP_TOOLS = 15
_TOP_OUTPUTS = 5
_RECENT_SESSIONS = 5
# Edit/Write: el payload del hook trae el archivo entero, que no entra al
# contexto; los eventos previos a `context_tokens` se cuentan como acuse.
_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
_EDIT_ACK_TOKENS = 20
# Cuántas tool calls después de un recorte se considera que una repetición
# fue "para recuperar lo omitido" (y no una consulta nueva e independiente).
_MISS_WINDOW = 8


def telemetry_scopes(root: Path) -> list[str]:
    """Prefijos de key posibles para el proyecto: project_id y hash de la raíz host."""
    scopes = [cached_project_id(root)]
    try:
        host_root = discovery.canonical_project_path(root)
    except ValueError:
        host_root = root
    scopes.append(hashlib.sha256(str(host_root).encode("utf-8")).hexdigest()[:16])
    return [scope for scope in dict.fromkeys(scopes) if scope]


async def load_telemetry(root: Path) -> list[dict]:
    """Eventos de telemetría del proyecto en Redis; [] si Redis no responde."""
    client = memory._get_client()
    entries: list[dict] = []
    try:
        for scope in telemetry_scopes(root):
            async for key in client.scan_iter(match=f"{_TELEMETRY_PREFIX}:{scope}:*"):
                for raw in await client.lrange(key, 0, -1):
                    try:
                        entries.append(json.loads(raw))
                    except json.JSONDecodeError:
                        continue
    except Exception as exc:  # noqa: BLE001 — best-effort, igual que memory.py
        memory._warn(f"no se pudo leer telemetría: {exc}")
    return entries


def _context_tokens(entry: dict) -> int:
    if "context_tokens" in entry:
        return int(entry.get("context_tokens") or 0)
    if entry.get("tool") in _EDIT_TOOLS:
        return _EDIT_ACK_TOKENS
    return int(entry.get("output_tokens") or 0)


def aggregate_usage(entries: list[dict]) -> dict[str, Any]:
    """Qué tools llenan el contexto y cuánto contexto usa cada sesión."""
    by_tool: dict[str, dict[str, int]] = defaultdict(lambda: {"calls": 0, "context_tokens": 0, "max": 0})
    sessions: dict[str, dict[str, Any]] = {}
    outputs: list[dict[str, Any]] = []
    for entry in entries:
        session = sessions.setdefault(
            entry.get("session_id", "unknown"),
            {"tool_calls": 0, "peak_context": 0, "last_context": 0, "last_ts": ""},
        )
        session["last_ts"] = max(session["last_ts"], entry.get("ts", ""))
        if entry.get("event") == "context_usage":
            tokens = int(entry.get("context_tokens") or 0)
            session["peak_context"] = max(session["peak_context"], tokens)
            session["last_context"] = tokens
        elif entry.get("event") == "tool_call":
            tokens = _context_tokens(entry)
            bucket = by_tool[entry.get("tool", "unknown")]
            bucket["calls"] += 1
            bucket["context_tokens"] += tokens
            bucket["max"] = max(bucket["max"], tokens)
            session["tool_calls"] += 1
            outputs.append({"tool": entry.get("tool", "unknown"), "context_tokens": tokens, "ts": entry.get("ts", "")})
    total = sum(bucket["context_tokens"] for bucket in by_tool.values())
    top_tools = sorted(by_tool.items(), key=lambda item: -item[1]["context_tokens"])[:_TOP_TOOLS]
    recent = sorted(sessions.items(), key=lambda item: item[1]["last_ts"], reverse=True)[:_RECENT_SESSIONS]
    return {
        "tool_calls": sum(bucket["calls"] for bucket in by_tool.values()),
        "tool_context_tokens": total,
        "by_tool": {
            tool: {**bucket, "share_pct": round(100 * bucket["context_tokens"] / total, 1) if total else 0.0}
            for tool, bucket in top_tools
        },
        "top_outputs": sorted(outputs, key=lambda item: -item["context_tokens"])[:_TOP_OUTPUTS],
        "recent_sessions": [{"session_id": sid, **data} for sid, data in recent],
    }


def context_misses(entries: list[dict]) -> dict[str, Any]:
    """¿Los recortes de salida dejaron al agente sin el contexto que necesitaba?

    Un recorte (`truncated`: la salida traía [htx:omitted]) cuenta como miss
    si dentro de las siguientes `_MISS_WINDOW` tool calls de la sesión el
    agente repitió la misma llamada (misma `fingerprint`, sin contar
    parámetros de tamaño). Abrir el output completo guardado
    (`saved_output_lookup`) se cuenta aparte: es recuperar barato, no re-trabajo.
    `repeat_calls` mide re-trabajo general (misma llamada repetida sin recorte
    previo), típico tras perder contexto por compactación.
    """
    by_session: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        if entry.get("event") == "tool_call" and "fingerprint" in entry:
            by_session[entry.get("session_id", "unknown")].append(entry)

    by_tool: dict[str, dict[str, int]] = defaultdict(lambda: {"truncated": 0, "refetched": 0})
    repeats: dict[str, int] = defaultdict(int)
    truncated_total = refetched_total = lookups = 0
    for calls in by_session.values():
        seen: dict[str, bool] = {}
        for index, call in enumerate(calls):
            tool, fp = call.get("tool", "unknown"), call["fingerprint"]
            lookups += bool(call.get("saved_output_lookup"))
            if fp in seen and not seen[fp]:
                repeats[tool] += 1
            if call.get("truncated"):
                truncated_total += 1
                by_tool[tool]["truncated"] += 1
                window = calls[index + 1 : index + 1 + _MISS_WINDOW]
                if any(later["fingerprint"] == fp for later in window):
                    refetched_total += 1
                    by_tool[tool]["refetched"] += 1
            seen[fp] = bool(call.get("truncated"))
    return {
        "truncated_outputs": truncated_total,
        "refetched_after_truncation": refetched_total,
        "saved_output_lookups": lookups,
        "miss_rate_pct": round(100 * refetched_total / truncated_total, 1) if truncated_total else 0.0,
        "by_tool": dict(by_tool),
        "repeat_calls": dict(sorted(repeats.items(), key=lambda item: -item[1])[:10]),
    }


async def summarize_usage(root: Path) -> dict[str, Any]:
    entries = await load_telemetry(root)
    return {**aggregate_usage(entries), "context_misses": context_misses(entries)}


async def read_memory(root: Path) -> dict[str, Any]:
    """Memoria de ejecución del proyecto (Redis), más reciente primero."""
    entries = await memory.list_memory(root)
    return {"entries": entries}
