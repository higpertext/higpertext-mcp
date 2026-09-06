"""Render native wiring from HookService without copying policy scripts."""
from __future__ import annotations

import copy
import json
import re
import shlex
import warnings
from pathlib import Path

from higpertext_mcp import hook_protocol, profile_client

_SETTINGS_PATH = {
    "opencode": ".opencode/plugins/higpertext.js",
    "claude": ".claude/settings.json",
    "codex": ".codex/hooks.json",
    "gemini": ".gemini/settings.json",
    "copilot": ".github/hooks/higpertext.json",
    "antigravity": ".agents/hooks.json",
}
_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")


def _managed(entry: dict) -> bool:
    command = entry.get("command", entry.get("bash", ""))
    if not isinstance(command, str):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    # Only the exact console-script invocation is ours, never a shell pipeline.
    if len(parts) == 2:
        return parts[0] == "higpertext-hook" and bool(_ID.fullmatch(parts[1]))
    return (len(parts) == 6 and parts[0] == "higpertext-hook"
            and bool(_ID.fullmatch(parts[1])) and parts[2] == "--assistant"
            and parts[3] in _SETTINGS_PATH and parts[4] == "--event"
            and parts[5] in hook_protocol.EVENTS[parts[3]])


def _clean(groups: dict) -> dict:
    """Remove only managed entries, preserving mixed groups and their attributes."""
    result = {}
    for event, entries in groups.items():
        if not isinstance(entries, list):
            raise ValueError(f"hooks.{event} must be an array")
        kept = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"hooks.{event} entries must be objects")
            if "hooks" in entry:
                if not isinstance(entry["hooks"], list) or not all(isinstance(h, dict) for h in entry["hooks"]):
                    raise ValueError("group hooks must be an array of objects")
                children = [h for h in entry["hooks"] if not _managed(h)]
                if children or not entry["hooks"]:
                    kept.append({**entry, "hooks": children})
            elif not _managed(entry):
                kept.append(entry)
        if kept or not entries:
            result[event] = kept
    return result


def _plan(config: dict, assistant: str, hooks: list) -> dict:
    config = copy.deepcopy(config)
    if assistant == "antigravity":
        for name in list(config):
            if name.startswith("higpertext:"):
                definition = config[name]
                if not isinstance(definition, dict):
                    raise ValueError(f"invalid hook definition: {name}")
                events = {k: v for k, v in definition.items() if k != "enabled"}
                cleaned = _clean(events)
                if cleaned:
                    config[name] = {**cleaned, **({"enabled": definition["enabled"]} if "enabled" in definition else {})}
                else:
                    del config[name]
        grouped = {}
    else:
        if not isinstance(config.get("hooks", {}), dict):
            raise ValueError("hooks must be an object")
        grouped = _clean(config.get("hooks", {}))
        if assistant == "copilot":
            if config.get("version", 1) != 1:
                raise ValueError("unsupported Copilot hooks version")
            config["version"] = 1
    for hook in hooks:
        if not _ID.fullmatch(hook.id):
            raise ValueError("hook id is not a safe command identifier")
        if hook.event not in hook_protocol.EVENTS[assistant]:
            raise ValueError(f"{assistant}: unsupported event {hook.event} for {hook.id}")
        if hook.timeout < 0:
            raise ValueError("hook timeout cannot be negative")
        event = hook_protocol.EVENTS[assistant][hook.event]
        command = f"higpertext-hook {hook.id} --assistant {assistant} --event {hook.event}"
        handler = {"type": "command", "command": command}
        matcher = hook_protocol.native_matcher(assistant, hook.matcher)
        if assistant == "copilot":
            handler.update(timeoutSec=hook.timeout)
            if hook.matcher:
                handler["matcher"] = matcher
            entry = handler
        else:
            handler["timeout"] = hook.timeout * (1000 if assistant == "gemini" else 1)
            if assistant == "gemini":
                handler["name"] = hook.id
            entry = {"hooks": [handler]}
            if hook.event in {"PreToolUse", "PostToolUse"}:
                entry["matcher"] = matcher
        if assistant == "antigravity":
            if hook.event not in {"PreToolUse", "PostToolUse"}:
                entry = handler
            name = f"higpertext:{hook.id}"
            definition = config.setdefault(name, {})
            definition.setdefault(event, []).append(entry)
        else:
            grouped.setdefault(event, []).append(entry)
    if assistant != "antigravity":
        config["hooks"] = grouped
    return config


async def render(root: Path, profile: str, assistants: list[str]) -> dict[str, list[str]]:
    selected = list(dict.fromkeys(assistants)) or list(_SETTINGS_PATH)
    invalid = set(selected) - set(_SETTINGS_PATH)
    if invalid:
        raise ValueError(f"hook adapters not supported: {', '.join(sorted(invalid))}; OpenCode requires a version-specific plugin bridge")
    plans = []
    # Validate every destination before touching any file.
    for assistant in selected:
        hooks = await profile_client.list_hooks(profile, assistant)
        path = root / _SETTINGS_PATH[assistant]
        if assistant == "opencode":
            config = _opencode_plan(path, hooks)
        else:
            config = _plan(_load_json(path), assistant, hooks)
        if any(h.id == "hook_security_guard_post" for h in hooks):
            warnings.warn(f"{assistant}: output redaction is not certified; PostToolUse wiring alone does not guarantee removal of original output", stacklevel=2)
        plans.append((assistant, path, config))
    result = {}
    for assistant, path, config in plans:
        if assistant == "opencode":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(config, encoding="utf-8")
        else:
            _save_json(path, config)
        result[assistant] = [str(path.relative_to(root))]
    return result


_OPENCODE_HEADER = "// Generated by higpertext: OpenCode classic tool.execute API.\n"


def _opencode_plan(path: Path, hooks: list) -> str:
    if path.exists() and not path.read_text(encoding="utf-8").startswith(_OPENCODE_HEADER):
        raise ValueError(f"refusing to replace unmanaged OpenCode plugin: {path}")
    definitions = []
    for hook in hooks:
        if not _ID.fullmatch(hook.id) or hook.timeout < 0:
            raise ValueError("invalid OpenCode hook id or timeout")
        if hook.event not in hook_protocol.EVENTS["opencode"]:
            raise ValueError(f"OpenCode classic does not support {hook.event}")
        definitions.append({"id": hook.id, "event": hook.event,
                            "matcher": hook_protocol.native_matcher("opencode", hook.matcher),
                            "timeout": hook.timeout})
    return _OPENCODE_HEADER + "import { spawnSync } from 'node:child_process';\n" + "const hooks = " + json.dumps(definitions) + ";\n" + r"""
export const HigpertextHooks = async ({ directory }) => {
  const invoke = (event, input, output) => {
    for (const hook of hooks) {
      if (hook.event !== event || !new RegExp(hook.matcher).test(input.tool)) continue;
      const payload = { hook_event_name: event, tool_name: input.tool,
        tool_input: event === 'PreToolUse' ? output.args : input.args,
        tool_response: output.output, cwd: directory };
      const result = spawnSync('higpertext-hook', [hook.id, '--assistant', 'opencode', '--event', event],
        { input: JSON.stringify(payload), encoding: 'utf8', cwd: directory,
          timeout: hook.timeout > 0 ? hook.timeout * 1000 : 10000,
          maxBuffer: 4 * 1024 * 1024, windowsHide: true });
      if (result.error || result.status !== 0) throw new Error('higpertext hook execution failed');
      const decision = JSON.parse(result.stdout);
      const specific = decision.hookSpecificOutput || {};
      if (decision.continue === false || ['deny', 'ask'].includes(specific.permissionDecision)) {
        throw new Error(specific.permissionDecisionReason || 'Blocked by higpertext');
      }
      if (event === 'PostToolUse' && specific.additionalContext) {
        output.output = (output.output || '') + '\n' + specific.additionalContext;
      }
    }
  };
  return {
    'tool.execute.before': async (input, output) => invoke('PreToolUse', input, output),
    'tool.execute.after': async (input, output) => invoke('PostToolUse', input, output),
  };
};
"""
