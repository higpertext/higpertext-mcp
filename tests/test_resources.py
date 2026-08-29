import json
import tempfile
from pathlib import Path

from higpertext_mcp import resources


def _make_project_with_telemetry(entries: list[dict]) -> Path:
    root = Path(tempfile.mkdtemp())
    state_dir = root / ".higpertext" / "state"
    state_dir.mkdir(parents=True)
    lines = [json.dumps(e) for e in entries]
    (state_dir / "telemetry.jsonl").write_text("\n".join(lines), encoding="utf-8")
    return root


def test_no_telemetry_file_returns_zeroed_summary():
    root = Path(tempfile.mkdtemp())
    summary = resources.summarize_usage(root)
    assert summary == {"total_tokens": 0, "total_cost_usd": 0.0, "calls": 0, "by_tool": {}}


def test_aggregates_tokens_and_cost_by_tool():
    root = _make_project_with_telemetry(
        [
            {"event": "tool_call", "tool": "Bash", "estimated_tokens": 10, "estimated_cost_usd": 0.001},
            {"event": "tool_call", "tool": "Bash", "estimated_tokens": 5, "estimated_cost_usd": 0.0005},
            {"event": "tool_call", "tool": "Read", "estimated_tokens": 20, "estimated_cost_usd": 0.002},
        ]
    )
    summary = resources.summarize_usage(root)
    assert summary["total_tokens"] == 35
    assert summary["by_tool"]["Bash"]["calls"] == 2
    assert summary["by_tool"]["Read"]["tokens"] == 20


def test_ignores_non_tool_call_events():
    root = _make_project_with_telemetry([{"event": "session_start"}])
    summary = resources.summarize_usage(root)
    assert summary["total_tokens"] == 0


def test_ignores_malformed_json_lines():
    root = _make_project_with_telemetry([{"event": "tool_call", "tool": "Bash", "estimated_tokens": 1}])
    path = root / ".higpertext" / "state" / "telemetry.jsonl"
    path.write_text(path.read_text(encoding="utf-8") + "\n{not valid json", encoding="utf-8")
    summary = resources.summarize_usage(root)
    assert summary["total_tokens"] == 1
