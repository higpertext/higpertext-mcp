import base64
from pathlib import Path

import pytest

from higpertext_mcp import dispatch, schema
from higpertext_mcp.gen.profile.v1 import profile_pb2

_GREP_SEARCH_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "higpertext-cli"
    / "src"
    / "higpertext"
    / "capabilities"
    / "common"
    / "scripts"
    / "core"
    / "search"
    / "grep_search.py"
)


def test_params_to_argv_skips_none_values():
    argv = dispatch._params_to_argv("common.grep-search", {"pattern": "foo", "path": None})
    assert argv == ["common.grep-search", "--pattern", "foo"]


def test_params_to_argv_stringifies_values():
    argv = dispatch._params_to_argv("common.grep-search", {"max_results": 5})
    assert argv == ["common.grep-search", "--max_results", "5"]


@pytest.mark.anyio
async def test_call_capability_real_grep_search_on_this_repo(monkeypatch, tmp_path):
    """Requiere higpertext-cli instalado editable + correr desde un checkout real.

    Redis/profile server se stubean acá: el registro de actividad es una
    preocupación aparte, ya cubierta por test_memory.py/test_profile_client.py.
    El script en sí ya no viene del JSON local — se simula la respuesta del
    profile server (`get_capability_script`) con el .py real leído de disco,
    igual que haría el import tool contra higpertext-cli.
    """
    recorded: list[tuple] = []

    async def fake_record_memory(root, **kwargs):
        recorded.append(("memory", kwargs))

    async def fake_record_activity(**kwargs):
        recorded.append(("activity", kwargs))

    async def fake_get_capability_script(capability_id):
        source_code = base64.b64encode(_GREP_SEARCH_SCRIPT.read_bytes()).decode()
        return source_code, "python", {}

    monkeypatch.setattr(dispatch.memory, "record_memory", fake_record_memory)
    monkeypatch.setattr(dispatch.profile_client, "record_activity", fake_record_activity)
    monkeypatch.setattr(dispatch.profile_client, "get_capability_script", fake_get_capability_script)
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(tmp_path))

    cap = profile_pb2.Capability(
        id="common.grep-search",
        entrypoint="capabilities/common/scripts/core/search/grep_search.py",
        language="python",
        parameters=[
            profile_pb2.Parameter(name="pattern", required=False),
            profile_pb2.Parameter(name="path", required=False, default="."),
            profile_pb2.Parameter(name="max_results", required=False, default="100"),
        ],
    )
    capability_data = schema.tool_spec_from_capability(cap).raw
    result = await dispatch.call_capability(
        "common.grep-search",
        {"pattern": "def call_capability", "path": "src", "max_results": "5"},
        capability_data,
    )
    assert result.ok
    assert "call_capability" in result.summary
    assert "text" in result.data
    assert result.error is None
    assert {kind for kind, _ in recorded} == {"memory", "activity"}
