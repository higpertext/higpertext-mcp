"""Ingesta incremental de los logs nativos de Codex y Claude hacia Redis."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from higpertext_mcp import memory


def _key(path: Path) -> str:
    return hashlib.sha256(str(path).encode()).hexdigest()[:24]


async def _offset(path: Path) -> int:
    try:
        raw = await memory._get_client().get(f"higpertext:collector:offset:{_key(path)}")
        return int(raw or 0)
    except Exception:  # best effort
        return 0


async def _set_offset(path: Path, value: int) -> None:
    try:
        await memory._get_client().set(f"higpertext:collector:offset:{_key(path)}", value)
    except Exception:
        pass


def _codex_events(item: dict) -> tuple[str, str, str, dict] | None:
    payload = item.get("payload", {})
    session = payload.get("session_id") or payload.get("thread_id")
    turn = payload.get("turn_id", "session")
    if item.get("type") == "token_usage_record":
        return session, turn, "platform.tokens", {"assistant": "codex", "usage": payload.get("usage", {}), "turn_usage": payload.get("turn_token_usage", {})}
    if item.get("type") == "event_msg" and payload.get("type") == "item_completed":
        entry = payload.get("item", {})
        if entry.get("type") == "CommandExecution":
            return session, turn, "platform.command", {"assistant": "codex", "command": entry.get("command", []), "cwd": entry.get("cwd", ""), "status": entry.get("status", ""), "stdout": entry.get("stdout", "")}
    if item.get("type") == "response_item" and payload.get("type") == "custom_tool_call":
        return session, turn, "platform.tool_call", {"assistant": "codex", "tool": payload.get("name"), "call_id": payload.get("call_id"), "input": payload.get("input", "")}
    return None


def _claude_event(item: dict) -> tuple[str, str, str, dict] | None:
    if item.get("type") != "assistant" or not isinstance(item.get("message"), dict):
        return None
    usage = item["message"].get("usage")
    if not usage:
        return None
    session = item.get("sessionId") or item.get("session_id") or "unknown"
    turn = item.get("uuid") or item.get("timestamp", "session")
    return session, turn, "platform.tokens", {"assistant": "claude", "usage": usage}


async def _ingest_file(root: Path, path: Path, parser) -> int:
    start = await _offset(path)
    try:
        size = path.stat().st_size
        if size < start:
            start = 0
        with path.open("r", encoding="utf-8") as stream:
            stream.seek(start)
            lines = stream.readlines()
            end = stream.tell()
    except OSError:
        return 0
    imported = 0
    for line in lines:
        try:
            event = parser(json.loads(line))
        except json.JSONDecodeError:
            continue
        if not event or not event[0]:
            continue
        session, turn, name, data = event
        await memory.record_trace_event(root, trace_id=f"{data['assistant']}:{session}:{turn}", event=name, data=data)
        imported += 1
    await _set_offset(path, end)
    return imported


def _codex_matches_root(path: Path, root: Path) -> bool:
    """Evita importar sesiones Codex de otro proyecto montadas en el mismo HOME."""
    try:
        with path.open("r", encoding="utf-8") as stream:
            for _ in range(20):
                item = json.loads(stream.readline())
                if item.get("type") == "session_meta":
                    cwd = item.get("payload", {}).get("cwd", "")
                    # Dentro de Docker la raíz es /workspace, mientras que el
                    # log conserva el cwd del host. El nombre final mantiene
                    # el aislamiento por proyecto sin depender de la CLI.
                    host_root = os.environ.get("HIGPERTEXT_HOST_PROJECT_ROOT", "")
                    return cwd == host_root or cwd == str(root) or Path(cwd).name == root.name
    except (OSError, json.JSONDecodeError):
        return False
    return False


async def ingest(root: Path) -> dict[str, int]:
    """Importa líneas nuevas de la sesión del proyecto, sin releer el historial."""
    result = {"codex": 0, "claude": 0}
    codex_dir = Path(os.environ.get("HIGPERTEXT_CODEX_LOG_DIR", "/host-home/.codex/sessions"))
    for path in codex_dir.rglob("*.jsonl") if codex_dir.exists() else []:
        if _codex_matches_root(path, root):
            result["codex"] += await _ingest_file(root, path, _codex_events)
    claude_base = Path(os.environ.get("HIGPERTEXT_CLAUDE_LOG_DIR", "/host-home/.claude/projects"))
    project_dir = claude_base / str(root).replace("/", "-")
    for path in project_dir.glob("*.jsonl") if project_dir.exists() else []:
        result["claude"] += await _ingest_file(root, path, _claude_event)
    return result
