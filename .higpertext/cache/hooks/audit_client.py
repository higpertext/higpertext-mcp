"""Cliente best-effort del AuditService del profile server.

Usado por los hooks que toman una decisión de enforcement (deny/warn) para
dejar un registro de auditoría centralizado en cuanto deciden — ver
hook_bash_guard.py y hook_security_guard_pre.py — y por hook_audit.py para
el camino "allow" (todo lo que efectivamente llegó a ejecutarse).

Nunca debe tumbar el hook que lo llama: cualquier error (import faltante,
red caída, timeout, o un profile server viejo que todavía no expone
AuditService porque no fue rebuildeado) se traga en silencio, igual que
_resolve_project_id en hook_session_stop.py. Un registro de auditoría
perdido es preferible a una sesión de trabajo interrumpida.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _resolve_actor() -> str:
    """Identidad best-effort de quien disparó la acción. No es autenticación
    real (nada impide que alguien mienta su git config o su $USER) — es la
    mejor señal disponible sin infraestructura de identidad propia. Ver
    limitación documentada en el diseño del "auth hook" pendiente."""
    try:
        out = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True, text=True, timeout=1,
        )
        email = out.stdout.strip()
        if email:
            return email
    except Exception:  # noqa: BLE001 — git no instalado, sin repo, timeout, etc.
        pass
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def record(
    *,
    event: str,
    tool_name: str,
    hook_id: str,
    decision: str,
    root: Path,
    rule_id: str = "",
    weight: int = 0,
    summary: str = "",
    profile: str = "",
    project_id: str = "",
    user_id: str = "",
) -> None:
    """Manda un AuditEvent al profile server. Best-effort total: nunca lanza."""
    try:
        import higpertext_mcp
        import sys
        sys.path.insert(0, str(Path(higpertext_mcp.__file__).parent / "gen"))
        from higpertext_mcp.gen.profile.v1 import profile_pb2, profile_pb2_grpc
        import grpc as _grpc
    except ImportError:
        return

    addr = os.environ.get("HIGPERTEXT_PROFILE_SERVER_ADDR", "localhost:50051")
    try:
        channel = _grpc.insecure_channel(addr)
        stub = profile_pb2_grpc.AuditServiceStub(channel)
        stub.RecordAuditEvent(
            profile_pb2.RecordAuditEventRequest(
                event=event,
                tool_name=tool_name,
                hook_id=hook_id,
                rule_id=rule_id,
                decision=decision,
                weight=weight,
                summary=summary[:500],
                actor=_resolve_actor(),
                profile=profile,
                project_id=project_id,
                user_id=user_id,
            ),
            timeout=2,
        )
        channel.close()
    except Exception:  # noqa: BLE001 — profile server caído o sin AuditService (viejo) no debe tumbar el hook
        pass
