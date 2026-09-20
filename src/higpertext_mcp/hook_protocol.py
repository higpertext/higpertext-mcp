"""Transport adapters; hook implementations and policies remain in HookService."""
from __future__ import annotations

import json

from higpertext_mcp import events
from higpertext_mcp import adapter_catalog

EVENTS = {name: dict(spec.hook_events) for name, spec in adapter_catalog.ADAPTERS.items()}
TOOLS = {name: dict(spec.tool_aliases) for name, spec in adapter_catalog.ADAPTERS.items()}


def native_matcher(assistant: str, matcher: str) -> str:
    """Translate the canonical literal alternatives, without rewriting regex fragments."""
    if not matcher:
        return ".*"
    return "|".join(dict.fromkeys(TOOLS[assistant].get(t, t) for t in matcher.split("|")))


def normalize(assistant: str, event: str, payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("hook input must be a JSON object")
    result = dict(payload)
    if assistant == "antigravity":
        call = payload.get("toolCall", {})
        name, args = call.get("name", ""), call.get("args", {})
        roots = payload.get("workspacePaths", [])
        result["cwd"] = args.get("Cwd") or (roots[0] if len(roots) == 1 else "")
    elif assistant == "copilot":
        name = payload.get("toolName", payload.get("tool_name", ""))
        args = payload.get("toolArgs", payload.get("tool_input", {}))
        result["tool_response"] = payload.get("toolResult", payload.get("tool_result", {}))
    else:
        name, args = payload.get("tool_name", ""), payload.get("tool_input", {})
    if isinstance(args, str):
        args = json.loads(args)
    if not isinstance(args, dict):
        raise ValueError("hook tool arguments must be an object")
    args = dict(args)
    for canonical, native in TOOLS[assistant].items():
        if name in native.split("|"):
            name = canonical
            break
    if "command" not in args and "CommandLine" in args:
        args["command"] = args["CommandLine"]
    for key in ("filePath", "filepath", "path", "AbsolutePath", "TargetFile"):
        if "file_path" not in args and key in args:
            args["file_path"] = args[key]
    canonical = events.canonical_type(assistant, event)
    result.update(
        hook_event_name=event,
        canonical_event=canonical.value,
        event_observation="observed",
        tool_name=name,
        tool_input=args,
    )
    return result


def encode(assistant: str, event: str, output: dict) -> dict:
    if not isinstance(output, dict):
        raise ValueError("hook output must be a JSON object")
    specific = output.get("hookSpecificOutput", {})
    denied = specific.get("permissionDecision") in {"deny", "ask"} or output.get("continue") is False or output.get("decision") in {"deny", "block"}
    reason = specific.get("permissionDecisionReason") or specific.get("additionalContext") or output.get("reason") or output.get("error") or "Blocked by higpertext hook"
    context = specific.get("additionalContext", "")
    native_event = EVENTS[assistant][event]
    if assistant in {"claude", "codex", "opencode"}:
        if denied and event == "PreToolUse":
            return {"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny", "permissionDecisionReason": reason}}
        if event == "PreToolUse" and "updatedInput" in specific and "permissionDecision" not in specific:
            normalized = dict(output)
            normalized_specific = dict(specific)
            normalized_specific["hookEventName"] = event
            normalized_specific["permissionDecision"] = "allow"
            normalized["hookSpecificOutput"] = normalized_specific
            return normalized
        return output
    if assistant == "gemini":
        if denied:
            return {"decision": "deny", "reason": reason}
        return {"hookSpecificOutput": {"hookEventName": native_event, "additionalContext": context}} if context else {}
    if assistant == "copilot":
        if event == "PreToolUse" and denied:
            return {"permissionDecision": "deny", "permissionDecisionReason": reason}
        if event == "Stop" and denied:
            return {"decision": "block", "reason": reason}
        return {"additionalContext": context} if context else {}
    if assistant == "antigravity":
        if event == "PreToolUse" and denied:
            return {"decision": "deny", "reason": reason}
        # Empty output abstains. Never automatically grant native permissions.
        return {}
    raise ValueError(f"unsupported hook protocol: {assistant}")
