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


@pytest.mark.anyio
async def test_update_task_forwards_acceptance_criteria_replacement(monkeypatch):
    requests = []

    class FakeChannel:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    class FakeTaskService:
        async def UpdateTask(self, request, timeout):
            requests.append(request)
            return type("Response", (), {"task": board_client.board_pb2.Task(id=request.id, title=request.title)})()

    monkeypatch.setattr(board_client.grpc.aio, "insecure_channel", lambda *_: FakeChannel())
    monkeypatch.setattr(board_client.board_pb2_grpc, "TaskServiceStub", lambda _: FakeTaskService())

    await board_client.update_task(task_id="t1", title="Task", done=False, acceptance_criteria=["rollback"])
    assert requests[-1].replace_acceptance_criteria is True
    assert [criterion.description for criterion in requests[-1].acceptance_criteria] == ["rollback"]

    await board_client.update_task(task_id="t1", title="Task", done=False)
    assert requests[-1].replace_acceptance_criteria is False
    assert list(requests[-1].acceptance_criteria) == []

    await board_client.update_task(task_id="t1", title="Task", done=False, acceptance_criteria=[])
    assert requests[-1].replace_acceptance_criteria is True
    assert list(requests[-1].acceptance_criteria) == []


@pytest.mark.anyio
async def test_create_comment_trims_and_forwards_to_activity_service(monkeypatch):
    requests = []

    class FakeChannel:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    class FakeActivityService:
        async def CreateActivityComment(self, request, timeout):
            requests.append(request)
            comment = board_client.board_pb2.BoardComment(
                id="c1", board_activity_id=request.board_activity_id, text=request.text,
            )
            return type("Response", (), {"comment": comment})()

    monkeypatch.setattr(board_client.grpc.aio, "insecure_channel", lambda *_: FakeChannel())
    monkeypatch.setattr(board_client.board_pb2_grpc, "ActivityServiceStub", lambda _: FakeActivityService())

    result = await board_client.create_comment(board_activity_id=" a1 ", text="  hola  ")

    assert requests[0].board_activity_id == "a1"
    assert requests[0].text == "hola"
    assert result["id"] == "c1"
    assert result["board_activity_id"] == "a1"
    assert result["text"] == "hola"


@pytest.mark.anyio
async def test_propose_scenarios_forwards_authenticated_verification_spec(monkeypatch):
    requests = []

    class FakeChannel:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    class FakeVerificationService:
        async def ProposeScenarios(self, request, timeout):
            requests.append(request)
            return board_client.board_pb2.ProposeScenariosResponse(
                task=board_client.board_pb2.Task(id=request.task_id, title="task"), spec_hash="abc123",
            )

    monkeypatch.setattr(board_client.grpc.aio, "insecure_channel", lambda *_: FakeChannel())
    monkeypatch.setattr(board_client.board_pb2_grpc, "VerificationServiceStub", lambda _: FakeVerificationService())
    result = await board_client.propose_scenarios(
        task_id="task-1", author="user-verified", dry_run=True,
        scenarios=[{
            "criterion_id": "criterion-1", "kind": "SCENARIO_HAPPY", "title": "happy path",
            "steps": [{"name": "run", "command": "go test ./...", "expect_exit_code": 0, "output_contains": ["ok"]}],
        }],
    )
    assert result["spec_hash"] == "abc123"
    assert result["dry_run"] is True
    assert requests[0].author == "user-verified"
    assert requests[0].dry_run is True
    assert requests[0].scenarios[0].kind == board_client.board_pb2.SCENARIO_HAPPY
    assert requests[0].scenarios[0].steps[0].expect_exit_code == 0
    assert list(requests[0].scenarios[0].steps[0].output_contains) == ["ok"]
