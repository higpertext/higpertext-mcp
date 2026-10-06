"""RFC-0025: higpertext-hook-admin activa/desactiva un hook sin borrarlo ni recrearlo.

`set_enabled` llama a HookService.SetHookEnabled (solo cambia `enabled`) y `list`
puede incluir los hooks deshabilitados. Se prueba en dos niveles: el cliente gRPC
(`profile_client`, con un stub fake) y la herramienta MCP real sobre el protocolo."""

import json
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from higpertext_mcp import discovery, profile_client, server as server_module
from higpertext_mcp.gen.profile.v1 import profile_pb2


# ── cliente gRPC ────────────────────────────────────────────────────────────


class _FakeHookStub:
    def __init__(self) -> None:
        self.set_requests: list[profile_pb2.SetHookEnabledRequest] = []
        self.list_requests: list[profile_pb2.ListHooksRequest] = []

    async def SetHookEnabled(self, request, timeout=None):
        self.set_requests.append(request)
        hook = profile_pb2.HookDefinition(
            id=request.id, event="PreToolUse", enabled=request.enabled, priority=-200, profiles=["perfil-a"]
        )
        return profile_pb2.SetHookEnabledResponse(hook=hook)

    async def ListHooks(self, request, timeout=None):
        self.list_requests.append(request)
        hooks = [profile_pb2.HookDefinition(id="hook-on", enabled=True)]
        if request.include_disabled:
            hooks.append(profile_pb2.HookDefinition(id="hook-off", enabled=False))
        return profile_pb2.ListHooksResponse(hooks=hooks)


def _patch_hook_channel(monkeypatch, stub: _FakeHookStub) -> None:
    @asynccontextmanager
    async def fake_insecure_channel(_addr):
        yield object()

    monkeypatch.setattr(profile_client.grpc.aio, "insecure_channel", fake_insecure_channel)
    monkeypatch.setattr(profile_client.profile_pb2_grpc, "HookServiceStub", lambda _channel: stub)


@pytest.mark.anyio
async def test_set_hook_enabled_sends_only_id_and_enabled_and_returns_the_hook(monkeypatch):
    stub = _FakeHookStub()
    _patch_hook_channel(monkeypatch, stub)

    off = await profile_client.set_hook_enabled("hook_gate", False)
    on = await profile_client.set_hook_enabled("hook_gate", True)

    # enabled=false es el cero de proto3: tiene que llegar igualmente (no se omite).
    assert [(r.id, r.enabled) for r in stub.set_requests] == [("hook_gate", False), ("hook_gate", True)]
    assert off["enabled"] is False and on["enabled"] is True
    assert off["priority"] == -200 and off["profiles"] == ["perfil-a"]


@pytest.mark.anyio
async def test_list_hooks_raw_only_asks_for_disabled_ones_when_requested(monkeypatch):
    stub = _FakeHookStub()
    _patch_hook_channel(monkeypatch, stub)

    default = await profile_client.list_hooks_raw()
    everything = await profile_client.list_hooks_raw(include_disabled=True)

    assert [h["id"] for h in default] == ["hook-on"]
    assert [h["id"] for h in everything] == ["hook-on", "hook-off"]
    assert [r.include_disabled for r in stub.list_requests] == [False, True]


# ── herramienta MCP sobre el protocolo ──────────────────────────────────────


def _project_with_profile(monkeypatch) -> None:
    root = Path(tempfile.mkdtemp())
    config_dir = root / ".higpertext" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "environment.json").write_text(json.dumps({"active_profile": "dev"}), encoding="utf-8")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))

    async def fake_list_allowed(_profile):
        return []

    monkeypatch.setattr(discovery.profile_client, "list_allowed_capabilities", fake_list_allowed)


async def _call(monkeypatch, arguments: dict, **patches):
    _project_with_profile(monkeypatch)
    for name, fn in patches.items():
        monkeypatch.setattr(server_module.profile_client, name, fn)
    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        return await client.call_tool("higpertext-hook-admin", arguments)


def _forbidden(name: str):
    async def fail(*_args, **_kwargs):
        raise AssertionError(f"{name} no debía llamarse: activar/desactivar no borra ni recrea")

    return fail


def test_schema_exposes_set_enabled_and_include_disabled():
    schema = server_module._HOOK_TOOL.inputSchema
    assert "set_enabled" in schema["properties"]["action"]["enum"]
    assert schema["properties"]["include_disabled"]["type"] == "boolean"
    assert "set_enabled" in server_module._HOOK_TOOL.description


@pytest.mark.anyio
@pytest.mark.parametrize("enabled,verb", [(False, "desactivado"), (True, "activado")])
async def test_set_enabled_toggles_without_delete_or_create(monkeypatch, enabled, verb):
    calls = []

    async def fake_set(hook_id, value):
        calls.append((hook_id, value))
        return {"id": hook_id, "enabled": value, "event": "PreToolUse"}

    result = await _call(
        monkeypatch, {"action": "set_enabled", "id": "hook_gate", "enabled": enabled},
        set_hook_enabled=fake_set, delete_hook=_forbidden("delete_hook"), create_hook=_forbidden("create_hook"),
    )

    assert result.isError is False
    assert calls == [("hook_gate", enabled)]
    assert result.structuredContent["data"]["enabled"] is enabled
    assert verb in result.structuredContent["summary"] and "hook_gate" in result.structuredContent["summary"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "arguments",
    [
        {"action": "set_enabled", "id": "hook_gate"},                      # falta enabled: no hay default
        {"action": "set_enabled", "id": "hook_gate", "enabled": "false"},  # un string no es un booleano
        {"action": "set_enabled", "id": "hook_gate", "enabled": None},
        {"action": "set_enabled", "enabled": False},                       # falta id
    ],
)
async def test_set_enabled_requires_explicit_id_and_boolean(monkeypatch, arguments):
    result = await _call(monkeypatch, arguments, set_hook_enabled=_forbidden("set_hook_enabled"))

    assert result.isError is True
    assert result.structuredContent["ok"] is False


@pytest.mark.anyio
async def test_set_enabled_reports_server_errors(monkeypatch):
    async def failing(_hook_id, _enabled):
        raise RuntimeError("hook not found")

    result = await _call(monkeypatch, {"action": "set_enabled", "id": "no_existe", "enabled": False},
                         set_hook_enabled=failing)

    assert result.isError is True and "No se pudo administrar el hook" in result.structuredContent["summary"]


@pytest.mark.anyio
async def test_list_includes_disabled_only_when_asked(monkeypatch):
    seen = []

    async def fake_list(*args, **kwargs):
        seen.append(kwargs.get("include_disabled", False))
        hooks = [{"id": "global-on", "profiles": [], "enabled": True}]
        if kwargs.get("include_disabled"):
            hooks.append({"id": "global-off", "profiles": [], "enabled": False})
            hooks.append({"id": "scoped-off", "profiles": ["dev"], "enabled": False})
        return hooks

    default = await _call(monkeypatch, {"action": "list"}, list_hooks_raw=fake_list)
    everything = await _call(monkeypatch, {"action": "list", "include_disabled": True}, list_hooks_raw=fake_list)
    only_global = await _call(monkeypatch, {"action": "list_global", "include_disabled": True}, list_hooks_raw=fake_list)
    # include_disabled como string no es un booleano: el esquema lo rechaza antes de listar nada.
    stringy = await _call(monkeypatch, {"action": "list", "include_disabled": "true"}, list_hooks_raw=fake_list)

    assert [h["id"] for h in default.structuredContent["data"]["hooks"]] == ["global-on"]
    assert [h["id"] for h in everything.structuredContent["data"]["hooks"]] == ["global-on", "global-off", "scoped-off"]
    assert [h["id"] for h in only_global.structuredContent["data"]["hooks"]] == ["global-on", "global-off"]
    assert stringy.isError is True
    assert seen == [False, True, True]
