"""Contexto de correlación por llamada MCP."""
from __future__ import annotations

import contextvars
import uuid

_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("higpertext_trace_id", default=None)


def start() -> tuple[str, contextvars.Token]:
    trace_id = f"trc_{uuid.uuid4().hex}"
    return trace_id, _trace_id.set(trace_id)


def current() -> str:
    return _trace_id.get() or f"trc_{uuid.uuid4().hex}"


def reset(token: contextvars.Token) -> None:
    _trace_id.reset(token)
