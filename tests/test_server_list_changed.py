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

from higpertext_mcp import server as server_module


def _make_project(active_profile: str, capabilities: list[str]) -> Path:
    root = Path(tempfile.mkdtemp())
    config_dir = root / ".higpertext" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "environment.json").write_text(
        json.dumps({"active_profile": active_profile}), encoding="utf-8"
    )
    profiles_dir = root / "src" / "config" / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / f"{active_profile}.json").write_text(
        json.dumps({"capabilities": capabilities}), encoding="utf-8"
    )
    return root


@pytest.mark.anyio
async def test_profile_change_triggers_tool_list_changed_notification(monkeypatch):
    root = _make_project("dev", ["common.grep-search"])
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))

    received: list[object] = []

    async def message_handler(message):
        if isinstance(message, types.ServerNotification):
            received.append(message.root)

    server = server_module.build_server()
    async with create_connected_server_and_client_session(
        server, message_handler=message_handler
    ) as client:
        await client.list_tools()

        # El perfil gana una capability nueva a mitad de sesión.
        profiles_dir = root / "src" / "config" / "profiles"
        (profiles_dir / "dev.json").write_text(
            json.dumps({"capabilities": ["common.grep-search", "git.diff"]}),
            encoding="utf-8",
        )

        result = await client.call_tool("common.grep-search", {"pattern": "x"})
        assert result is not None

    kinds = [type(n).__name__ for n in received]
    assert "ToolListChangedNotification" in kinds
