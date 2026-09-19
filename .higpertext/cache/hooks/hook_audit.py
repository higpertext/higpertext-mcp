"""Hook PostToolUse (todos los tools) — el "audit hook": registra en
AuditService cada acción que efectivamente se ejecutó. Llegar a
PostToolUse implica que ningún hook PreToolUse la bloqueó, así que esto
cubre el lado "allow" del audit trail.

No duplica lo que hook_bash_guard.py / hook_security_guard_pre.py ya
registran inline en el momento de un block/warn (ver audit_client.py) —
sin este hook, el audit trail solo tendría la mitad "bloqueado", nunca la
mitad "permitido y ejecutado", que es la que en la práctica importa más
para una revisión de cumplimiento ("¿quién corrió qué, cuándo").

Limitación conocida: summary es el comando/input truncado tal cual llega
en el payload, SIN pasar por el masking de hook_security_guard_post — si
un comando trae un secreto inline (poco común, pero posible en un `export
X=...`), puede quedar en el registro de auditoría. No se reimplementa acá
el masking para no duplicar esa lógica; si esto se vuelve un problema real,
la solución es que este hook importe security_rules.mask_tool_output sobre
el summary antes de mandarlo, no reescribir el regex.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import audit_client
from .hook_io import hook_main, read_payload, read_tool_command, emit_continue
from .hook_utils import get_project_root, WORKSPACE_DIR_NAME


def _session_profile(root: Path) -> str:
    session_path = root / WORKSPACE_DIR_NAME / "state" / "session.json"
    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))
        return data.get("profile", "")
    except (OSError, json.JSONDecodeError):
        return ""


def _tool_name(payload: dict) -> str:
    return str(payload.get("tool_name") or payload.get("tool") or "")


@hook_main
def main() -> None:
    payload = read_payload()
    tool_name = _tool_name(payload)
    root = get_project_root()

    cmd = read_tool_command(payload)
    summary = cmd or json.dumps(payload.get("tool_input", {}), ensure_ascii=False)

    audit_client.record(
        event="PostToolUse",
        tool_name=tool_name,
        hook_id="hook_audit",
        decision="allow",
        root=root,
        summary=summary[:300],
        profile=_session_profile(root),
    )
    emit_continue()


if __name__ == "__main__":
    main()
