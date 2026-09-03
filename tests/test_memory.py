"""Cobertura de memory.py con un fake Redis in-process (sin red real) — mismo
criterio que `ExternalServerPool.from_sessions` usa para no depender de un
servidor externo en tests."""

from pathlib import Path

import pytest

from higpertext_mcp import memory


class _FakeRedis:
    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}

    async def lpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).insert(0, value)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        values = self.lists.get(key, [])
        self.lists[key] = values[start : end + 1] if end >= 0 else values[start:]

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        values = self.lists.get(key, [])
        return values if end == -1 else values[start : end + 1]


@pytest.fixture(autouse=True)
def _fake_client(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(memory, "_client", fake)
    monkeypatch.setattr(memory, "_get_client", lambda: fake)
    return fake


@pytest.mark.anyio
async def test_record_then_list_round_trips(tmp_path: Path):
    await memory.record_memory(tmp_path, action="Auto-run (MCP): common.grep-search", status="success", notes="ok")

    entries = await memory.list_memory(tmp_path)
    assert len(entries) == 1
    assert entries[0]["action"] == "Auto-run (MCP): common.grep-search"
    assert entries[0]["status"] == "success"


@pytest.mark.anyio
async def test_different_projects_do_not_share_memory(tmp_path: Path):
    project_a = tmp_path / "a"
    project_b = tmp_path / "b"
    project_a.mkdir()
    project_b.mkdir()

    await memory.record_memory(project_a, action="act-a", status="success")

    assert len(await memory.list_memory(project_a)) == 1
    assert await memory.list_memory(project_b) == []


@pytest.mark.anyio
async def test_record_memory_is_best_effort_on_redis_failure(tmp_path: Path, monkeypatch):
    class _BrokenRedis:
        async def lpush(self, *_args, **_kwargs):
            raise ConnectionError("redis down")

    monkeypatch.setattr(memory, "_get_client", lambda: _BrokenRedis())

    # No debe levantar excepción — best-effort.
    await memory.record_memory(tmp_path, action="act", status="failure")


@pytest.mark.anyio
async def test_list_memory_is_empty_on_redis_failure(tmp_path: Path, monkeypatch):
    class _BrokenRedis:
        async def lrange(self, *_args, **_kwargs):
            raise ConnectionError("redis down")

    monkeypatch.setattr(memory, "_get_client", lambda: _BrokenRedis())

    assert await memory.list_memory(tmp_path) == []
