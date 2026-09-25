import hashlib

import pytest

from higpertext_mcp import resources


def test_empty_telemetry_returns_zeroed_summary():
    summary = resources.aggregate_usage([])
    assert summary == {
        "tool_calls": 0,
        "tool_context_tokens": 0,
        "by_tool": {},
        "top_outputs": [],
        "recent_sessions": [],
    }


def test_aggregates_context_tokens_by_tool():
    summary = resources.aggregate_usage(
        [
            {"event": "tool_call", "tool": "Bash", "context_tokens": 10, "session_id": "s"},
            {"event": "tool_call", "tool": "Bash", "context_tokens": 30, "session_id": "s"},
            {"event": "tool_call", "tool": "Read", "context_tokens": 60, "session_id": "s"},
        ]
    )
    assert summary["tool_context_tokens"] == 100
    assert summary["by_tool"]["Bash"] == {"calls": 2, "context_tokens": 40, "max": 30, "share_pct": 40.0}
    assert list(summary["by_tool"]) == ["Read", "Bash"]
    assert summary["top_outputs"][0]["tool"] == "Read"


def test_legacy_events_without_context_tokens_do_not_inflate_edits():
    summary = resources.aggregate_usage(
        [
            {"event": "tool_call", "tool": "Edit", "output_tokens": 5000},
            {"event": "tool_call", "tool": "Bash", "output_tokens": 700},
        ]
    )
    assert summary["by_tool"]["Edit"]["context_tokens"] == 20
    assert summary["by_tool"]["Bash"]["context_tokens"] == 700


def test_tracks_peak_and_last_context_per_session():
    summary = resources.aggregate_usage(
        [
            {"event": "context_usage", "context_tokens": 90_000, "session_id": "a", "ts": "2026-09-25T01"},
            {"event": "context_usage", "context_tokens": 150_000, "session_id": "a", "ts": "2026-09-25T02"},
            {"event": "context_usage", "context_tokens": 60_000, "session_id": "a", "ts": "2026-09-25T03"},
            {"event": "context_usage", "context_tokens": 40_000, "session_id": "b", "ts": "2026-09-24T01"},
        ]
    )
    first, second = summary["recent_sessions"]
    assert first == {
        "session_id": "a", "tool_calls": 0, "peak_context": 150_000, "last_context": 60_000, "last_ts": "2026-09-25T03",
    }
    assert second["session_id"] == "b"


def test_telemetry_scopes_use_project_id_and_host_root_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(resources, "cached_project_id", lambda root: "proj-1")
    expected_hash = hashlib.sha256(str(tmp_path.resolve()).encode("utf-8")).hexdigest()[:16]
    assert resources.telemetry_scopes(tmp_path) == ["proj-1", expected_hash]


@pytest.mark.anyio
async def test_load_telemetry_is_best_effort_when_redis_fails(tmp_path, monkeypatch):
    class Broken:
        def scan_iter(self, **_kwargs):
            raise ConnectionError("down")

    monkeypatch.setattr(resources.memory, "_get_client", lambda: Broken())
    assert await resources.load_telemetry(tmp_path) == []


def _call(fp, truncated=False, tool="Bash", session="s", lookup=False):
    return {"event": "tool_call", "tool": tool, "fingerprint": fp, "truncated": truncated,
            "saved_output_lookup": lookup, "session_id": session}


def test_context_misses_counts_refetch_after_truncation_only_within_window():
    entries = [
        _call("Bash:pytest", truncated=True),
        _call("Read:a"),
        _call("Bash:pytest"),  # repitió lo recortado -> miss
        _call("Bash:make", truncated=True),
        *[_call(f"Read:{i}") for i in range(8)],
        _call("Bash:make"),  # fuera de la ventana -> no es miss
        _call("Bash:grep x /tmp/higpertext-outputs/1.log", lookup=True),
    ]
    misses = resources.context_misses(entries)
    assert misses["truncated_outputs"] == 2
    assert misses["refetched_after_truncation"] == 1
    assert misses["miss_rate_pct"] == 50.0
    assert misses["saved_output_lookups"] == 1
    assert misses["by_tool"]["Bash"] == {"truncated": 2, "refetched": 1}


def test_context_misses_reports_repeats_without_truncation_per_session():
    entries = [_call("Read:a", tool="Read"), _call("Read:a", tool="Read"), _call("Read:a", tool="Read", session="other")]
    misses = resources.context_misses(entries)
    assert misses["repeat_calls"] == {"Read": 1}
    assert misses["truncated_outputs"] == 0 and misses["miss_rate_pct"] == 0.0


def test_context_misses_ignores_legacy_events_without_fingerprint():
    assert resources.context_misses([{"event": "tool_call", "tool": "Bash"}])["truncated_outputs"] == 0
