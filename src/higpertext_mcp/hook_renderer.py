"""Materializa hooks nativos desde HookService, sin higpertext-cli."""
from __future__ import annotations

import base64
import json
from pathlib import Path

from higpertext_mcp import profile_client

HOOK_DIRS = {
    "claude": ".claude/hooks",
    "codex": ".codex/hooks",
    "gemini": ".gemini/hooks",
    "opencode": ".opencode/hooks",
}


def _write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} debe contener un objeto JSON")
    return value


def _save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def render(root: Path, profile: str, assistants: list[str]) -> dict[str, list[str]]:
    """Escribe hooks aplicables; devuelve archivos por adapter para auditoría."""
    result: dict[str, list[str]] = {}
    for assistant in assistants:
        if assistant not in HOOK_DIRS:
            continue
        hooks, sources, assets = await profile_client.hook_bundle(profile, assistant)
        directory = root / HOOK_DIRS[assistant]
        written: list[str] = []
        scripts: list[tuple[object, Path]] = []
        for hook in hooks:
            filename = Path(hook.script).name or f"{hook.id}.py"
            destination = directory / filename
            _write(destination, base64.b64decode(sources[hook.id]))
            scripts.append((hook, destination))
            written.append(str(destination.relative_to(root)))
        for relative, source in assets.items():
            destination = directory / relative
            _write(destination, base64.b64decode(source))
            written.append(str(destination.relative_to(root)))
        if assistant == "claude":
            path = root / ".claude/settings.json"
            config = _load_json(path)
            grouped: dict[str, list[dict]] = {}
            for hook, script in scripts:
                grouped.setdefault(hook.event, []).append({
                    "matcher": hook.matcher or ".*",
                    "hooks": [{"type": "command", "command": f"python3 {script}", "timeout": hook.timeout}],
                })
            config["hooks"] = grouped
            _save_json(path, config)
            written.append(str(path.relative_to(root)))
        elif assistant == "codex":
            path = root / ".codex/hooks.json"
            config = _load_json(path)
            grouped: dict[str, list[dict]] = {}
            for hook, script in scripts:
                entry = {"type": "command", "command": f"python3 {script}", "timeout": hook.timeout}
                group = {"hooks": [entry]}
                if hook.matcher and hook.event not in {"UserPromptSubmit", "Stop"}:
                    group["matcher"] = hook.matcher
                grouped.setdefault(hook.event, []).append(group)
            config["hooks"] = grouped
            _save_json(path, config)
            written.append(str(path.relative_to(root)))
        elif assistant == "gemini":
            path = root / ".gemini/settings.json"
            config = _load_json(path)
            config["hooks"] = {
                hook.event: [{"matcher": hook.matcher or ".*", "hooks": [{"name": hook.id, "type": "command", "command": f"python3 {script}", "timeout": hook.timeout * 1000}]}]
                for hook, script in scripts
            }
            _save_json(path, config)
            written.append(str(path.relative_to(root)))
        result[assistant] = written
    return result
