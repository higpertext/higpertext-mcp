"""Hook PreToolUse:Bash — evalúa todas las reglas de comandos Bash en cadena.

v2: separa explícitamente dos etapas — "precondition" (check_hard_blocks,
check_deployment_gate: peso fijo 5, no negociable, jamás degradan) y
"policy" (check_profile_rules: peso 1-5 leído de la GovernanceRule que
originó cada entrada de profile_rules.json, puede resolver en block o en
context/warn). Cada decisión de block/warn se registra en AuditService
antes de emitirse — ver audit_client.py. El camino "allow" (comandos que
efectivamente corrieron) lo cubre hook_audit.py en PostToolUse: este hook
no lo duplica.
"""

from __future__ import annotations
from ._rules.bash_rules import (
    RuleResult,
    is_whitelisted,
    check_hard_blocks,
    check_deployment_gate,
    check_profile_rules,
)
from .hook_utils import get_project_root, WORKSPACE_DIR_NAME
from .hook_io import (
    hook_main,
    read_payload,
    read_tool_command,
    emit_continue,
    emit_deny,
    emit_context,
)
from . import audit_client
import json
from pathlib import Path

# (nombre de etapa, función) en orden de evaluación. El nombre de etapa es
# informativo (queda solo en comentarios/lectura humana del código, no se
# manda al audit trail) — lo que sí viaja es rule_id/weight de cada RuleResult.
_STAGES = [
    check_hard_blocks,
    check_deployment_gate,
    check_profile_rules,
]


def _session_profile(root: Path) -> str:
    session_path = root / WORKSPACE_DIR_NAME / "state" / "session.json"
    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
        return data.get("profile", "")
    except (OSError, json.JSONDecodeError):
        return ""


@hook_main
def main() -> None:
    payload = read_payload()
    cmd = read_tool_command(payload)
    if not cmd:
        emit_continue()
        return

    root = get_project_root()

    if is_whitelisted(cmd):
        emit_continue()
        return

    profile = _session_profile(root)

    for rule_fn in _STAGES:
        result: RuleResult | None = rule_fn(cmd, root)
        if result is None:
            continue

        if result.severity in ("block", "context"):
            audit_client.record(
                event="PreToolUse",
                tool_name="Bash",
                hook_id="hook_bash_guard",
                decision="block" if result.severity == "block" else "warn",
                root=root,
                rule_id=result.rule_id,
                weight=result.weight,
                summary=cmd[:300],
                profile=profile,
            )

        if result.severity == "block":
            emit_deny("PreToolUse", result.message)
            return

        if result.severity == "context":
            emit_context("PreToolUse", result.message)
            return

    emit_continue()


if __name__ == "__main__":
    main()
