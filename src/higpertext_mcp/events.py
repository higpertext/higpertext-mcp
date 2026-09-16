"""Canonical events shared by transports and execution boundaries.

Native hook names belong to adapters.  Consumers of the domain use this
catalog instead, so a platform-specific event can never become a security
guarantee by accident.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EventType(str, Enum):
    SESSION_STARTED = "SESSION_STARTED"
    PROMPT_RECEIVED = "PROMPT_RECEIVED"
    PLAN_CREATED = "PLAN_CREATED"
    ACTION_REQUESTED = "ACTION_REQUESTED"
    ACTION_AUTHORIZED = "ACTION_AUTHORIZED"
    ACTION_STARTED = "ACTION_STARTED"
    ACTION_COMPLETED = "ACTION_COMPLETED"
    ACTION_FAILED = "ACTION_FAILED"
    CONTEXT_COMPACTING = "CONTEXT_COMPACTING"
    SESSION_FINISHED = "SESSION_FINISHED"


@dataclass(frozen=True)
class CanonicalEvent:
    """Transport-neutral observation of something that happened."""

    type: EventType
    source_platform: str
    source_event: str
    payload: dict[str, Any]
    observed: bool = True
    enforcement: str = "observation"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.type.value,
            "source_platform": self.source_platform,
            "source_event": self.source_event,
            "payload": self.payload,
            "observed": self.observed,
            "enforcement": self.enforcement,
        }


@dataclass(frozen=True)
class AdapterCapabilities:
    """What an adapter can observe, not what it is allowed to enforce."""

    platform: str
    native_events: dict[str, EventType]
    unsupported: tuple[EventType, ...]
    limitations: tuple[str, ...]


_COMMON_LIMITATIONS = (
    "ACTION_AUTHORIZED is decided by the gateway/controller, never by a hook.",
    "Hook availability does not guarantee that an action was blocked or executed.",
)


ADAPTERS: dict[str, AdapterCapabilities] = {
    "claude": AdapterCapabilities(
        "claude",
        {
            "PreToolUse": EventType.ACTION_REQUESTED,
            "PostToolUse": EventType.ACTION_COMPLETED,
            "UserPromptSubmit": EventType.PROMPT_RECEIVED,
            "PreCompact": EventType.CONTEXT_COMPACTING,
            "Stop": EventType.SESSION_FINISHED,
        },
        (EventType.SESSION_STARTED, EventType.PLAN_CREATED, EventType.ACTION_AUTHORIZED),
        _COMMON_LIMITATIONS,
    ),
    "codex": AdapterCapabilities(
        "codex",
        {
            "PreToolUse": EventType.ACTION_REQUESTED,
            "PostToolUse": EventType.ACTION_COMPLETED,
            "UserPromptSubmit": EventType.PROMPT_RECEIVED,
            "PreCompact": EventType.CONTEXT_COMPACTING,
            "Stop": EventType.SESSION_FINISHED,
        },
        (EventType.SESSION_STARTED, EventType.PLAN_CREATED, EventType.ACTION_AUTHORIZED),
        _COMMON_LIMITATIONS,
    ),
    "opencode": AdapterCapabilities(
        "opencode",
        {"PreToolUse": EventType.ACTION_REQUESTED, "PostToolUse": EventType.ACTION_COMPLETED},
        (
            EventType.SESSION_STARTED,
            EventType.PROMPT_RECEIVED,
            EventType.PLAN_CREATED,
            EventType.ACTION_AUTHORIZED,
            EventType.CONTEXT_COMPACTING,
            EventType.SESSION_FINISHED,
        ),
        _COMMON_LIMITATIONS,
    ),
    "gemini": AdapterCapabilities(
        "gemini",
        {
            "PreToolUse": EventType.ACTION_REQUESTED,
            "PostToolUse": EventType.ACTION_COMPLETED,
            "UserPromptSubmit": EventType.PROMPT_RECEIVED,
            "PreCompact": EventType.CONTEXT_COMPACTING,
        },
        (EventType.SESSION_STARTED, EventType.PLAN_CREATED, EventType.ACTION_AUTHORIZED, EventType.SESSION_FINISHED),
        _COMMON_LIMITATIONS,
    ),
    "copilot": AdapterCapabilities(
        "copilot",
        {
            "PreToolUse": EventType.ACTION_REQUESTED,
            "PostToolUse": EventType.ACTION_COMPLETED,
            "UserPromptSubmit": EventType.PROMPT_RECEIVED,
            "PreCompact": EventType.CONTEXT_COMPACTING,
            "Stop": EventType.SESSION_FINISHED,
        },
        (EventType.SESSION_STARTED, EventType.PLAN_CREATED, EventType.ACTION_AUTHORIZED),
        _COMMON_LIMITATIONS,
    ),
    "antigravity": AdapterCapabilities(
        "antigravity",
        {
            "PreToolUse": EventType.ACTION_REQUESTED,
            "PostToolUse": EventType.ACTION_COMPLETED,
            "Stop": EventType.SESSION_FINISHED,
        },
        (
            EventType.SESSION_STARTED,
            EventType.PROMPT_RECEIVED,
            EventType.PLAN_CREATED,
            EventType.ACTION_AUTHORIZED,
            EventType.CONTEXT_COMPACTING,
        ),
        _COMMON_LIMITATIONS,
    ),
}


def canonical_type(platform: str, native_event: str) -> EventType:
    try:
        return ADAPTERS[platform].native_events[native_event]
    except KeyError as exc:
        raise ValueError(f"{platform}: native event {native_event!r} is not supported") from exc


def adapter_capabilities(platform: str) -> AdapterCapabilities:
    try:
        return ADAPTERS[platform]
    except KeyError as exc:
        raise ValueError(f"adapter not supported: {platform}") from exc
