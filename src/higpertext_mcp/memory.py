"""Memoria de ejecución respaldada en Redis — reemplaza los archivos estáticos
`.memory/journal.json` que antes escribía `save_memory()` del motor higpertext-cli.

Cada proyecto (root resuelto por `discovery.resolve_project_root()`) tiene su
propia lista Redis, acotada a `_MAX_ENTRIES` (más reciente primero, vía
LPUSH+LTRIM). Best-effort en toda la superficie pública: un Redis caído nunca
debe tumbar una respuesta MCP — mismo criterio fail-open-pero-silencioso que
`_save_memory_best_effort` tenía para el motor.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import redis.asyncio as redis

from higpertext_mcp import config

_MAX_ENTRIES = 500
_KEY_PREFIX = "higpertext:memory"

_client: redis.Redis | None = None


def _warn(message: str) -> None:
    print(f"[higpertext-mcp/memory] {message}", file=sys.stderr)


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(config.redis_url(), decode_responses=True)
    return _client


def _project_key(root: Path) -> str:
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    return f"{_KEY_PREFIX}:{digest}:journal"


async def record_memory(
    root: Path, *, action: str, status: str, notes: str = "", tags: list[str] | None = None
) -> None:
    """Registra una entrada de memoria. Best-effort: nunca levanta excepción."""
    entry = {
        "id": f"act_{int(time.time())}_{uuid.uuid4().hex[:4]}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "action": action,
        "status": status,
        "notes": notes,
        "tags": tags or ["general"],
    }
    try:
        client = _get_client()
        key = _project_key(root)
        await client.lpush(key, json.dumps(entry, ensure_ascii=False))
        await client.ltrim(key, 0, _MAX_ENTRIES - 1)
    except Exception as exc:  # noqa: BLE001 — Redis caído no debe tumbar el server MCP
        _warn(f"no se pudo registrar memoria en Redis: {exc}")


async def list_memory(root: Path) -> list[dict[str, Any]]:
    """Lee toda la memoria del proyecto (más reciente primero). [] si Redis no responde."""
    try:
        client = _get_client()
        raw_entries = await client.lrange(_project_key(root), 0, -1)
    except Exception as exc:  # noqa: BLE001
        _warn(f"no se pudo leer memoria de Redis: {exc}")
        return []

    entries: list[dict[str, Any]] = []
    for raw in raw_entries:
        try:
            entries.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return entries
