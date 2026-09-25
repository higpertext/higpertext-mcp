"""Valida que el server avisa tools/list_changed cuando el perfil activo
cambia mid-session (por ejemplo, el usuario corre `htx profile load` a mitad
de conversación) — sin esto el cliente se queda con la lista de tools vieja
hasta que reinicia el server."""

import json
import tempfile
from pathlib import Path

import mcp.types as types
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from higpertext_mcp import discovery, dispatch, server as server_module
from higpertext_mcp.gen.profile.v1 import profile_pb2


def _make_project(active_profile: str) -> Path:
    root = Path(tempfile.mkdtemp())
    config_dir = root / ".higpertext" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "environment.json").write_text(
        json.dumps({"active_profile": active_profile}), encoding="utf-8"
    )
    return root


@pytest.mark.anyio
async def test_profile_change_triggers_tool_list_changed_notification(monkeypatch):
    root = _make_project("dev")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))

    grep_search = profile_pb2.Capability(
        id="common.grep-search", parameters=[profile_pb2.Parameter(name="pattern")]
    )
    git_diff = profile_pb2.Capability(id="git.diff")
    granted = [grep_search]

    async def fake_list_allowed(profile):
        return list(granted) if profile == "dev" else []

    monkeypatch.setattr(discovery.profile_client, "list_allowed_capabilities", fake_list_allowed)

    async def fake_call_capability(*_args):
        return dispatch.CapabilityResult(
            ok=True, summary="ok", data={}, artifacts=[], warnings=[]
        )

    monkeypatch.setattr(dispatch, "call_capability", fake_call_capability)

    received: list[object] = []

    async def message_handler(message):
        if isinstance(message, types.ServerNotification):
            received.append(message.root)

    server = server_module.build_server()
    async with create_connected_server_and_client_session(
        server, message_handler=message_handler
    ) as client:
        await client.list_tools()

        # El perfil gana una capability nueva a mitad de sesión (el profile
        # server ahora refleja eso — acá lo simulamos mutando el stub).
        granted.append(git_diff)

        result = await client.call_tool("common-grep-search", {"pattern": "x"})
        assert result is not None

    kinds = [type(n).__name__ for n in received]
    assert "ToolListChangedNotification" in kinds
