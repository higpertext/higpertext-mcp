"""Salidas compactas hacia el agente y selección de proyecto por request."""

import json

import pytest

from higpertext_mcp import adapter_renderer, discovery, dispatch, server


def _result(ok=True, data=None, error=None, warnings=None):
    return dispatch.CapabilityResult(
        ok=ok,
        summary="line 1" if ok else "[ERROR] path no existe: /x (causa real)",
        data=data if data is not None else {},
        artifacts=[],
        warnings=warnings or [],
        error=error,
        trace_id="trc_1",
    )


def test_text_result_goes_plain_without_envelope():
    result = server.capability_call_result(_result(data={"text": "line 1\nline 2"}))

    assert result.content[0].text == "line 1\nline 2"
    assert result.structuredContent is None
    assert result.meta == {"trace_id": "trc_1"}


def test_structured_result_drops_empty_fields_and_trace_id():
    result = server.capability_call_result(_result(data={"matches": ["a.py:1"]}))

    assert result.structuredContent == {"ok": True, "summary": "line 1", "data": {"matches": ["a.py:1"]}}


def test_error_result_shows_diagnostic_in_content():
    result = server.capability_call_result(_result(ok=False, error="[ERROR] path no existe: /x (causa real)"))

    assert result.isError is True
    assert "causa real" in result.content[0].text


def test_error_summary_keeps_full_diagnostic():
    assert dispatch._summary("[ERROR] x\nFileNotFoundError: y", ok=False) == "[ERROR] x\nFileNotFoundError: y"
    assert dispatch._summary("first\nsecond", ok=True) == "first"


def test_strip_decoration_removes_banners_but_keeps_content_and_json():
    text = "[GREP] x\n[*] Buscando en: a\n=====\n---\n### a.py\n  L 1: foo\n=====\n[FOUND] 1"
    assert dispatch._strip_decoration(text) == "[GREP] x\n---\n### a.py\n  L 1: foo\n[FOUND] 1"
    assert dispatch._strip_decoration('{"a": "====="}') == '{"a": "====="}'


def test_host_paths_are_translated_both_ways(monkeypatch, tmp_path):
    host = tmp_path / "host"
    mount = tmp_path / "mount"
    (mount / "proj").mkdir(parents=True)
    monkeypatch.setenv("HIGPERTEXT_HOST_PROJECTS_ROOT", str(host))
    monkeypatch.setenv("HIGPERTEXT_PROJECTS_MOUNT", str(mount))

    params = dispatch._localize_params({"path": f"{host}/proj/a.py", "mode": "range", "limit": 5})

    assert params == {"path": f"{mount}/proj/a.py", "mode": "range", "limit": 5}
    assert dispatch._hostify(f"see {mount}/proj/a.py") == f"see {host}/proj/a.py"


def test_hostify_translates_process_root_and_respects_boundaries(monkeypatch):
    monkeypatch.setenv("HIGPERTEXT_PROJECTS_MOUNT", "/projects")
    monkeypatch.setenv("HIGPERTEXT_HOST_PROJECTS_ROOT", "/home/u/src")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", "/workspace")
    monkeypatch.setenv("HIGPERTEXT_HOST_PROJECT_ROOT", "/home/u/src/server")

    out = dispatch._hostify(
        '{"roots_indexed": ["/workspace", "/projects/web"], "file": "/workspace/app/a.ts", '
        '"other": "/projects-old/x", "nested": "/data/projects/y"}'
    )

    assert out == (
        '{"roots_indexed": ["/home/u/src/server", "/home/u/src/web"], "file": "/home/u/src/server/app/a.ts", '
        '"other": "/projects-old/x", "nested": "/data/projects/y"}'
    )


def test_request_project_overrides_process_root(monkeypatch, tmp_path):
    host = tmp_path / "host"
    mount = tmp_path / "mount"
    (mount / "proj").mkdir(parents=True)
    monkeypatch.setenv("HIGPERTEXT_HOST_PROJECTS_ROOT", str(host))
    monkeypatch.setenv("HIGPERTEXT_PROJECTS_MOUNT", str(mount))
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(tmp_path))

    token = discovery.select_request_project(str(host / "proj"))
    try:
        assert discovery.resolve_project_root() == (mount / "proj").resolve()
    finally:
        discovery.reset_request_project(token)
    assert discovery.resolve_project_root() == tmp_path.resolve()


def test_request_project_rejects_invisible_root(monkeypatch, tmp_path):
    monkeypatch.delenv("HIGPERTEXT_HOST_PROJECTS_ROOT", raising=False)
    with pytest.raises(ValueError):
        discovery.select_request_project(str(tmp_path / "missing"))


def test_renderer_adds_project_header_to_existing_http_entry(tmp_path):
    path = tmp_path / ".mcp.json"
    path.write_text(json.dumps({"mcpServers": {"higpertext": {"type": "http", "url": "http://x/mcp/"}}}))

    adapter_renderer.render(tmp_path, ["claude"], "dev", [], [])

    entry = json.loads(path.read_text())["mcpServers"]["higpertext"]
    assert entry == {
        "type": "http",
        "url": "http://x/mcp/",
        "headers": {discovery.PROJECT_ROOT_HEADER: str(tmp_path.resolve())},
    }


def test_claude_render_removes_rules_of_previous_profiles_only(tmp_path):
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "old_profile.md").write_text("x\n*configuración generada por la integración centralizada de adapters.*\n")
    (rules / "other.md").write_text(adapter_renderer.GENERATED_MARKER + "\n# Perfil higpertext: other\n")
    (rules / "seed.md").write_text("# seed\n\n*x — configuración auto-generada por render-hooks. No editar manualmente.*\n")
    (rules / "unmarked.md").write_text("# Perfil higpertext: viejo\n")
    (rules / "handwritten.md").write_text("# reglas propias del equipo\n")

    result = adapter_renderer.render(tmp_path, ["claude"], "dev", [], [])

    assert sorted(p.name for p in rules.glob("*.md")) == ["dev.md", "handwritten.md"]
    assert sorted(result["removed"]) == [
        ".claude/rules/old_profile.md", ".claude/rules/other.md", ".claude/rules/seed.md", ".claude/rules/unmarked.md",
    ]


def test_context_miss_replay_counts_truncations_whose_hidden_identifiers_are_used():
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location(
        "context_miss_replay", Path(__file__).parents[1] / "scripts" / "context_miss_replay.py"
    )
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    fake_filter = SimpleNamespace(
        _THRESHOLD_CHARS=0,
        summarize=lambda text: text if len(text) <= fake_filter._THRESHOLD_CHARS else text.splitlines()[0],
    )
    samples = [
        ("cat a.py", "head line\ndef load_config_file(): ...", "llamo a load_config_file()"),  # miss
        ("cat b.py", "head line\ndef other_helper(): ...", "no lo menciona"),  # recorte sin miss
        ("ls", "corto", ""),  # no se recorta
    ]

    stats = replay.replay(samples, fake_filter, threshold=10)

    assert stats["truncated"] == 2
    assert stats["misses"] == 1
