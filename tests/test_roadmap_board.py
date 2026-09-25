import json

import pytest

from higpertext_mcp import board_client, roadmap_board


@pytest.mark.anyio
async def test_migrate_local_roadmap_creates_status_columns_and_tasks(monkeypatch, tmp_path):
    config_dir = tmp_path / ".higpertext"
    config_dir.mkdir()
    (config_dir / "roadmap.json").write_text(json.dumps({
        "title": "Producto",
        "phases": [{
            "id": "phase-one", "name": "Primera fase", "description": "desc",
            "status": "active", "skills": ["common.build"], "tasks": ["Probar"],
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(roadmap_board.board_client, "resolve_board", lambda **_: _async({"id": "b1", "name": "Roadmap"}))
    monkeypatch.setattr(roadmap_board.board_client, "list_columns", lambda _id: _async([
        {"id": "pending", "name": "Pending"}, {"id": "active", "name": "Active"}, {"id": "done", "name": "Done"},
    ]))
    monkeypatch.setattr(roadmap_board.board_client, "list_activities", lambda _id: _async([]))
    created = []

    async def fake_create_activity(**kwargs):
        created.append(kwargs)
        return {"id": "a1", "title": kwargs["title"], "tags": kwargs["tags"]}

    monkeypatch.setattr(roadmap_board.board_client, "create_activity", fake_create_activity)
    monkeypatch.setattr(roadmap_board.board_client, "create_task", lambda **kwargs: _async({"id": "t1", **kwargs}))

    result = await roadmap_board.migrate_local_roadmap(root=tmp_path, project_id="p1", board_name="Roadmap")

    assert result["created_count"] == 1
    assert result["skipped_count"] == 0
    assert created[0]["column_id"] == "active"
    assert created[0]["tags"] == ["roadmap:phase-one", "common.build"]


async def _async(value):
    return value

