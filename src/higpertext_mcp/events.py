"""Canonical events shared by transports and execution boundaries.

Native hook names belong to adapters.  Consumers of the domain use this
catalog instead, so a platform-specific event can never become a security
guarantee by accident.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from higpertext_mcp import adapter_catalog


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


_EVENT_TYPES = {
    "PreToolUse": EventType.ACTION_REQUESTED,
    "PostToolUse": EventType.ACTION_COMPLETED,
    "UserPromptSubmit": EventType.PROMPT_RECEIVED,
    "Stop": EventType.SESSION_FINISHED,
    "PreCompact": EventType.CONTEXT_COMPACTING,
}


def _capabilities(spec: adapter_catalog.AdapterSpec) -> AdapterCapabilities:
    native_events = {event: _EVENT_TYPES[event] for event in spec.hook_events if event in _EVENT_TYPES}
    supported = set(native_events.values())
    unsupported = tuple(event for event in EventType if event not in supported)
    limitations = _COMMON_LIMITATIONS + spec.limitations
    return AdapterCapabilities(spec.id, native_events, unsupported, limitations)


ADAPTERS: dict[str, AdapterCapabilities] = {
    name: _capabilities(spec) for name, spec in adapter_catalog.ADAPTERS.items()
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
