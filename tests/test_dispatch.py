import pytest

from higpertext_mcp import dispatch, schema


def test_params_to_argv_skips_none_values():
    argv = dispatch._params_to_argv("common.grep-search", {"pattern": "foo", "path": None})
    assert argv == ["common.grep-search", "--pattern", "foo"]


def test_params_to_argv_stringifies_values():
    argv = dispatch._params_to_argv("common.grep-search", {"max_results": 5})
    assert argv == ["common.grep-search", "--max_results", "5"]


@pytest.mark.anyio
async def test_call_capability_real_grep_search_on_this_repo(monkeypatch):
    """Requiere higpertext-cli instalado editable + correr desde un checkout real.

    Redis/profile server se stubean acá: el registro de actividad es una
    preocupación aparte, ya cubierta por test_memory.py/test_profile_client.py.
    """
    recorded: list[tuple] = []

    async def fake_record_memory(root, **kwargs):
        recorded.append(("memory", kwargs))

    async def fake_record_activity(**kwargs):
        recorded.append(("activity", kwargs))

    monkeypatch.setattr(dispatch.memory, "record_memory", fake_record_memory)
    monkeypatch.setattr(dispatch.profile_client, "record_activity", fake_record_activity)

    capability_data = schema.load_tool_spec("common.grep-search").raw
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
