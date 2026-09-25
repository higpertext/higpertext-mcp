import base64

import pytest

from higpertext_mcp import runner


@pytest.mark.anyio
async def test_resolve_script_writes_entrypoint_and_extra_files(monkeypatch, tmp_path):
    async def fake_get_capability_script(capability_id):
        source = base64.b64encode(b"print('entrypoint')").decode()
        helper = base64.b64encode(b"def resolve_root():\n    return None\n").decode()
        return source, "python", {"_report_paths.py": helper}

    monkeypatch.setattr(runner.profile_client, "get_capability_script", fake_get_capability_script)
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(tmp_path))
    runner._script_cache.clear()

    path = await runner.resolve_script("common.commit-report")

    assert path.read_text() == "print('entrypoint')"
    helper_path = path.parent / "_report_paths.py"
    assert helper_path.exists()
    assert "resolve_root" in helper_path.read_text()


@pytest.mark.anyio
async def test_resolve_script_is_cached_per_process(monkeypatch, tmp_path):
    calls = []

    async def fake_get_capability_script(capability_id):
        calls.append(capability_id)
        source = base64.b64encode(b"print(1)").decode()
        return source, "python", {}

    monkeypatch.setattr(runner.profile_client, "get_capability_script", fake_get_capability_script)
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(tmp_path))
    runner._script_cache.clear()

    first = await runner.resolve_script("common.grep-search")
    second = await runner.resolve_script("common.grep-search")

    assert first == second
    assert calls == ["common.grep-search"]


@pytest.mark.anyio
async def test_resolve_script_cache_isolated_between_projects(monkeypatch, tmp_path):
    calls = []

    async def fake_get_capability_script(capability_id):
        calls.append(capability_id)
        source = base64.b64encode(f"print({len(calls)})".encode()).decode()
        return source, "python", {}

    monkeypatch.setattr(runner.profile_client, "get_capability_script", fake_get_capability_script)
    runner._script_cache.clear()
    project_a = tmp_path / "a"
    project_b = tmp_path / "b"
    project_a.mkdir()
    project_b.mkdir()

    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(project_a))
    path_a = await runner.resolve_script("common.grep-search")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(project_b))
    path_b = await runner.resolve_script("common.grep-search")

    assert path_a != path_b
    assert path_a.parent != path_b.parent
    assert path_a.read_text() == "print(1)"
    assert path_b.read_text() == "print(2)"
    assert calls == ["common.grep-search", "common.grep-search"]


@pytest.mark.anyio
async def test_resolve_script_rejects_helper_path_escape(monkeypatch, tmp_path):
    async def fake_get_capability_script(_capability_id):
        source = base64.b64encode(b"print(1)").decode()
        helper = base64.b64encode(b"secret").decode()
        return source, "python", {"../outside.py": helper}

    monkeypatch.setattr(runner.profile_client, "get_capability_script", fake_get_capability_script)
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(tmp_path))
    runner._script_cache.clear()

    with pytest.raises(ValueError, match="fuera del cache"):
        await runner.resolve_script("custom.escape")
    assert not (tmp_path / ".higpertext/cache/outside.py").exists()
