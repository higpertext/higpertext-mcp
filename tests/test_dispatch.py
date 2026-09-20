import pytest

from higpertext_mcp import dispatch, events, schema
from higpertext_mcp.gen.profile.v1 import profile_pb2


def test_params_to_argv_skips_none_values():
    argv = dispatch._params_to_argv("common.grep-search", {"pattern": "foo", "path": None})
    assert argv == ["common.grep-search", "--pattern", "foo"]


def test_params_to_argv_stringifies_values():
    argv = dispatch._params_to_argv("common.grep-search", {"max_results": 5})
    assert argv == ["common.grep-search", "--max_results", "5"]


def test_params_to_argv_serializes_rich_values_for_legacy_scripts():
    argv = dispatch._params_to_argv(
        "common.grep-search", {"include": ["py", "ts"], "regex": True}
    )
    assert argv == ["common.grep-search", "--include", "py,ts", "--regex", "true"]


@pytest.mark.anyio
async def test_call_capability_records_canonical_lifecycle(monkeypatch, tmp_path):
    trace = []

    async def record_trace_event(root, *, trace_id, event, data=None):
        trace.append(event)

    async def resolve_script(_capability_id):
        return tmp_path / "capability.py"

    monkeypatch.setattr(dispatch.discovery, "resolve_project_root", lambda: tmp_path)
    monkeypatch.setattr(dispatch.memory, "record_trace_event", record_trace_event)
    monkeypatch.setattr(dispatch.runner, "resolve_script", resolve_script)
    async def record_activity(*_args, **_kwargs):
        return None

    monkeypatch.setattr(dispatch, "_record_activity_best_effort", record_activity)
    monkeypatch.setattr(
        dispatch.execution,
        "run_inprocess",
        lambda fn, args: dispatch.execution.ExecutionResult(0, "[SUCCESS] done", ""),
    )

    result = await dispatch.call_capability("example.action", {}, {"parameters": []})

    assert result.ok
    assert trace == [
        events.EventType.ACTION_REQUESTED.value,
        events.EventType.ACTION_STARTED.value,
        events.EventType.ACTION_COMPLETED.value,
    ]


@pytest.mark.anyio
async def test_call_capability_real_grep_search_on_this_repo(monkeypatch, tmp_path):
    """common.grep-search ya no tiene fuente en disco en ningún checkout — vive
    100% en la DB del profile server (ver higpertext-capability). Este test
    necesita un profile server real corriendo (localhost:50051 por defecto)
    con esa capability importada; solo se stubea memory/activity, que es una
    preocupación aparte ya cubierta por test_memory.py/test_profile_client.py.
    """
    recorded: list[tuple] = []

    async def fake_record_memory(root, **kwargs):
        recorded.append(("memory", kwargs))

    async def fake_record_activity(**kwargs):
        recorded.append(("activity", kwargs))

    monkeypatch.setattr(dispatch.memory, "record_memory", fake_record_memory)
    monkeypatch.setattr(dispatch.profile_client, "record_activity", fake_record_activity)
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
