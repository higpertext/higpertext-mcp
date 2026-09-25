"""Casos de uso del roadmap y tablero para el menú del frontend.

El profile server conserva la fuente persistente de boards, columnas,
actividades y tasks. Este módulo sólo compone ese contrato en respuestas que
un frontend puede pintar directamente y ofrece la migración idempotente del
roadmap JSON existente.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from higpertext_mcp import board_client

_STATUS_TO_COLUMN = {
    "pending": board_client.COLUMN_PENDING,
    "active": board_client.COLUMN_ACTIVE,
    "done": board_client.COLUMN_DONE,
}


def load_roadmap(root: Path) -> dict[str, Any]:
    path = root / ".higpertext" / "roadmap.json"
    if not path.is_file():
        raise FileNotFoundError(f"no existe el roadmap local: {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("phases"), list):
        raise ValueError(".higpertext/roadmap.json debe contener un objeto con phases[]")
    return document


async def board_overview(*, project_id: str, board_name: str) -> dict[str, Any]:
    board = await board_client.resolve_board(project_id=project_id, name=board_name)
    columns = await board_client.list_columns(board["id"])
    activities = await board_client.list_activities(board["id"])
    tasks_by_activity: dict[str, list[dict]] = {}
    for activity in activities:
        tasks_by_activity[activity["id"]] = await board_client.list_tasks(activity["id"])
    return {
        "board": board,
        "columns": columns,
        "activities": activities,
        "tasks": tasks_by_activity,
    }


async def migrate_local_roadmap(*, root: Path, project_id: str, board_name: str) -> dict[str, Any]:
    document = load_roadmap(root)
    board = await board_client.resolve_board(project_id=project_id, name=board_name)
    columns = await board_client.list_columns(board["id"])
    column_ids = {column["name"]: column["id"] for column in columns}
    activities = await board_client.list_activities(board["id"])
    existing_tags = {
        tag: activity for activity in activities for tag in activity.get("tags", [])
        if tag.startswith("roadmap:")
    }
    created: list[dict] = []
    skipped: list[dict] = []
    for phase in document["phases"]:
        if not isinstance(phase, dict) or not phase.get("id") or not phase.get("name"):
            raise ValueError("cada fase del roadmap debe tener id y name")
        phase_id = str(phase["id"])
        marker = f"roadmap:{phase_id}"
        if marker in existing_tags:
            skipped.append({"phase_id": phase_id, "activity": existing_tags[marker]})
            continue
        status = str(phase.get("status", "pending")).lower()
        column_name = _STATUS_TO_COLUMN.get(status, board_client.COLUMN_PENDING)
        column_id = column_ids.get(column_name)
        if not column_id:
            raise LookupError(f"el board no tiene la columna {column_name!r}")
        tags = [marker, *[str(skill) for skill in phase.get("skills", [])]]
        activity = await board_client.create_activity(
            board_id=board["id"],
            column_id=column_id,
            title=str(phase["name"]),
            description=str(phase.get("description", "")),
            priority=str(phase.get("priority", "PRIORITY_UNSPECIFIED")),
            tags=tags,
            item_type=str(phase.get("item_type", "ROADMAP")),
        )
        tasks = []
        for task_title in phase.get("tasks", []) or []:
            tasks.append(await board_client.create_task(
                board_activity_id=activity["id"], title=str(task_title)
            ))
        created.append({"phase": phase, "activity": activity, "tasks": tasks})
    return {
        "board": board,
        "source": str(root / ".higpertext" / "roadmap.json"),
        "created": created,
        "skipped": skipped,
        "created_count": len(created),
        "skipped_count": len(skipped),
    }
