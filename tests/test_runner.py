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
