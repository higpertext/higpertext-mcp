"""Materializa el wiring nativo de hooks (settings.json/hooks.json) para
claude/codex/gemini a partir de HookService — sin copiar ningún script: el
`command` generado es siempre `higpertext-hook <id>`, un console_script que
resuelve y cachea el hook real contra el profile server en runtime (ver
`hook_invoker.py`/`hook_runner.py`). Así una actualización del catálogo (o de
un hook individual) llega a todos los proyectos sin tener que re-renderizar
cada uno para refrescar copias de archivos.
"""
from __future__ import annotations

import json
from pathlib import Path

from higpertext_mcp import profile_client

_SETTINGS_PATH = {
    "claude": ".claude/settings.json",
    "codex": ".codex/hooks.json",
    "gemini": ".gemini/settings.json",
}


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


def _hook_command(hook_id: str) -> str:
    return f"higpertext-hook {hook_id}"


async def render(root: Path, profile: str, assistants: list[str]) -> dict[str, list[str]]:
    """Escribe el wiring de hooks aplicable; devuelve archivos por adapter para auditoría."""
    result: dict[str, list[str]] = {}
    for assistant in assistants:
        if assistant not in _SETTINGS_PATH:
            continue
        hooks = await profile_client.list_hooks(profile, assistant)
        path = root / _SETTINGS_PATH[assistant]
        config = _load_json(path)

        if assistant == "claude":
            grouped: dict[str, list[dict]] = {}
            for hook in hooks:
                grouped.setdefault(hook.event, []).append({
                    "matcher": hook.matcher or ".*",
                    "hooks": [{"type": "command", "command": _hook_command(hook.id), "timeout": hook.timeout}],
                })
            config["hooks"] = grouped
        elif assistant == "codex":
            grouped = {}
            for hook in hooks:
                entry = {"type": "command", "command": _hook_command(hook.id), "timeout": hook.timeout}
                group = {"hooks": [entry]}
                if hook.matcher and hook.event not in {"UserPromptSubmit", "Stop"}:
                    group["matcher"] = hook.matcher
                grouped.setdefault(hook.event, []).append(group)
            config["hooks"] = grouped
        elif assistant == "gemini":
            config["hooks"] = {
                hook.event: [{
                    "matcher": hook.matcher or ".*",
                    "hooks": [{"name": hook.id, "type": "command", "command": _hook_command(hook.id), "timeout": hook.timeout * 1000}],
                }]
                for hook in hooks
            }

        _save_json(path, config)
        result[assistant] = [str(path.relative_to(root))]
    return result
