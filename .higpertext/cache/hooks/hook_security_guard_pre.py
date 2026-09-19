"""Hook común de seguridad para PreToolUse y PostToolUse.

v2: las decisiones de PreToolUse (block/warn) quedan registradas en
AuditService antes de emitirse — ver audit_client.py. RuleResult de
_rules/security_rules.py no distingue una GovernanceRule concreta (no lee
profile_rules.json como hook_bash_guard), así que rule_id queda vacío y el
peso se infiere de la severity de salida: block=5 (mismo criterio que un
hard-block), warn=3. El lado PostToolUse (masking) no cambia — no es una
decisión de enforcement, es post-procesamiento del output.
"""

from __future__ import annotations

import json

from .hook_io import (
    hook_main,
    read_payload,
    read_tool_command,
    emit_block,
    emit_context,
    emit_continue,
)
from .hook_utils import get_project_root, WORKSPACE_DIR_NAME
from . import audit_client
from ._rules.security_rules import (
    evaluate_command_guard,
    evaluate_path_guard,
    mask_tool_output,
)


def _tool_name(payload: dict) -> str:
    return str(payload.get("tool_name") or payload.get("tool") or "")


def _session_profile(root):
    session_path = root / WORKSPACE_DIR_NAME / "state" / "session.json"
    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
        return data.get("profile", "")
    except (OSError, json.JSONDecodeError):
        return ""


def _emit_masked_output(message: str, replacement_output: str) -> None:
    print(
        json.dumps(
            {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": message,
                    "replacementOutput": replacement_output,
                },
            }
        )
    )


@hook_main
def main() -> None:
    payload = read_payload()
    event = payload.get("event", "PreToolUse")
    tool_name = _tool_name(payload)
    root = get_project_root()

    if event == "PreToolUse":
        if tool_name in {"Bash", "PowerShell"}:
            result = evaluate_command_guard(read_tool_command(payload), root)
        else:
            result = evaluate_path_guard(tool_name, payload.get("tool_input", {}))
        if result:
            decision = "block" if result.severity not in ("warn", "context") else "warn"
            audit_client.record(
                event="PreToolUse",
                tool_name=tool_name,
                hook_id="hook_security_guard_pre",
                decision=decision,
                root=root,
                weight=5 if decision == "block" else 3,
                summary=(read_tool_command(payload) or json.dumps(payload.get("tool_input", {}), ensure_ascii=False))[:300],
                profile=_session_profile(root),
            )
            if result.severity in ("warn", "context"):
                emit_context("PreToolUse", result.message)
                return
            emit_block("PreToolUse", result.message)
            return
        emit_continue()
        return

    if event == "PostToolUse":
        result = mask_tool_output(payload.get("tool_response", {}), root)
        if result:
            _emit_masked_output(result.message, result.replacement_output)
            return
    emit_continue()


if __name__ == "__main__":
    main()
