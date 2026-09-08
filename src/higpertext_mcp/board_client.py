"""Cliente gRPC hacia board.v1 (higpertext-server-profile) — tablero ágil de
actividades usado para migrar el roadmap de .higpertext/roadmap.json (archivo
plano) a un modelo Board -> Column -> BoardActivity -> Task real.

Mismo patrón que profile_client.py: canal gRPC por-request (sin pool),
_CALL_TIMEOUT_S fijo, sin fallback silencioso en mutaciones — cualquier error
gRPC se propaga al caller (tool handler en server.py), que decide cómo
reportarlo. board.v1 corre en el mismo proceso/puerto que profile.v1
(config.profile_server_addr()), aunque vive en su propia base (board.db) y
paquete proto propio, aislado a propósito para una futura extracción a
microservicio — este cliente solo depende del contrato gRPC, nunca de
detalles internos de board.db.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path
from typing import Any, Coroutine

import grpc

sys.path.insert(0, str(Path(__file__).parent / "gen"))

from higpertext_mcp import config
from higpertext_mcp.gen.board.v1 import board_pb2, board_pb2_grpc

_CALL_TIMEOUT_S = 2.0


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Corre una corrutina desde código sync, sin asumir que el hilo actual
    esté libre de event loop. Las capabilities de roadmap corren dentro de
    dispatch.call_capability (async), que invoca runner.run_module de forma
    SÍNCRONA dentro de ese mismo hilo/loop (execution.run_inprocess llama
    fn() directo, sin thread pool) — un asyncio.run() directo ahí explota
    con "cannot be called from a running event loop". Cuando SÍ hay un loop
    corriendo en este hilo, delega a un hilo nuevo con su propio loop
    (asyncio.run es seguro en un hilo aparte); si no hay loop corriendo
    (ej. correr el script standalone para debug), usa asyncio.run directo.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def _target() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 — se re-lanza en el hilo llamante
            error["exc"] = exc

    thread = threading.Thread(target=_target)
    thread.start()
    thread.join()
    if "exc" in error:
        raise error["exc"]
    return result["value"]

# Nombres de columna fijos que ResolveBoard crea siempre (ver
# domain.BoardColumnPending/Active/Done en higpertext-server-profile) — las
# capabilities de roadmap resuelven la columna destino por este nombre en
# vez de hardcodear un id.
COLUMN_PENDING = "Pending"
COLUMN_ACTIVE = "Active"
COLUMN_DONE = "Done"


def _warn(message: str) -> None:
    print(f"[higpertext-mcp/board_client] {message}", file=sys.stderr)


def _board_to_dict(b: board_pb2.Board) -> dict:
    return {"id": b.id, "name": b.name, "description": b.description, "project_id": b.project_id}


def _column_to_dict(c: board_pb2.Column) -> dict:
    return {"id": c.id, "board_id": c.board_id, "name": c.name, "position": c.position}


def _activity_to_dict(a: board_pb2.BoardActivity) -> dict:
    return {
        "id": a.id,
        "board_id": a.board_id,
        "column_id": a.column_id,
        "title": a.title,
        "description": a.description,
        "assignee_user_id": a.assignee_user_id,
        "priority": board_pb2.Priority.Name(a.priority),
        "tags": list(a.tags),
        "position": a.position,
    }


def _task_to_dict(t: board_pb2.Task) -> dict:
    return {
        "id": t.id,
        "board_activity_id": t.board_activity_id,
        "title": t.title,
        "done": t.done,
        "position": t.position,
        "acceptance_criteria": [
            {"id": c.id, "description": c.description, "done": c.done} for c in t.acceptance_criteria
        ],
    }


async def resolve_board(*, project_id: str, name: str) -> dict:
    """Get-or-create idempotente por (project_id, name). Si el board no
    existía, el server crea además sus 3 columnas fijas (Pending/Active/Done)
    en la misma transacción — no hace falta crearlas acá."""
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = board_pb2_grpc.BoardServiceStub(channel)
        resp = await stub.ResolveBoard(
            board_pb2.ResolveBoardRequest(project_id=project_id, name=name), timeout=_CALL_TIMEOUT_S
        )
        return _board_to_dict(resp.board)


async def get_activity(activity_id: str) -> dict:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = board_pb2_grpc.ActivityServiceStub(channel)
        resp = await stub.GetActivity(board_pb2.GetActivityRequest(id=activity_id), timeout=_CALL_TIMEOUT_S)
        return _activity_to_dict(resp.activity)


async def list_columns(board_id: str) -> list[dict]:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = board_pb2_grpc.ColumnServiceStub(channel)
        resp = await stub.ListColumns(board_pb2.ListColumnsRequest(board_id=board_id), timeout=_CALL_TIMEOUT_S)
        return [_column_to_dict(c) for c in resp.columns]


async def resolve_column_id(board_id: str, column_name: str) -> str:
    """Resuelve el id de una columna por nombre (Pending/Active/Done) dentro
    de un board. LookupError si no existe — un board resuelto por
    resolve_board() siempre tiene las 3, así que esto solo falla ante un
    board_id equivocado o una columna borrada a mano."""
    columns = await list_columns(board_id)
    match = next((c for c in columns if c["name"] == column_name), None)
    if match is None:
        raise LookupError(f"el board {board_id!r} no tiene ninguna columna llamada {column_name!r}")
    return match["id"]


async def create_activity(
    *,
    board_id: str,
    column_id: str,
    title: str,
    description: str = "",
    assignee_user_id: str = "",
    priority: str = "PRIORITY_UNSPECIFIED",
    tags: list[str] | None = None,
) -> dict:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = board_pb2_grpc.ActivityServiceStub(channel)
        resp = await stub.CreateActivity(
            board_pb2.CreateActivityRequest(
                board_id=board_id,
                column_id=column_id,
                title=title,
                description=description,
                assignee_user_id=assignee_user_id,
                priority=board_pb2.Priority.Value(priority.upper()),
                tags=tags or [],
            ),
            timeout=_CALL_TIMEOUT_S,
        )
        return _activity_to_dict(resp.activity)


async def list_activities(board_id: str, column_id: str = "") -> list[dict]:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = board_pb2_grpc.ActivityServiceStub(channel)
        resp = await stub.ListActivities(
            board_pb2.ListActivitiesRequest(board_id=board_id, column_id=column_id), timeout=_CALL_TIMEOUT_S
        )
        return [_activity_to_dict(a) for a in resp.activities]


async def move_activity(*, activity_id: str, target_column_id: str, position: int = 0) -> dict:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = board_pb2_grpc.ActivityServiceStub(channel)
        resp = await stub.MoveActivity(
            board_pb2.MoveActivityRequest(id=activity_id, target_column_id=target_column_id, position=position),
            timeout=_CALL_TIMEOUT_S,
        )
        return _activity_to_dict(resp.activity)


async def create_task(*, board_activity_id: str, title: str, acceptance_criteria: list[str] | None = None) -> dict:
    """acceptance_criteria es una lista de descripciones (texto libre) — el
    server asigna id y done=false a cada una. Sin validación de "todos
    cumplidos" antes de marcar la Task done (deuda técnica aceptada a
    propósito, ver docs/api/task-service.md en higpertext-server-profile)."""
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = board_pb2_grpc.TaskServiceStub(channel)
        resp = await stub.CreateTask(
            board_pb2.CreateTaskRequest(
                board_activity_id=board_activity_id,
                title=title,
                acceptance_criteria=[
                    board_pb2.AcceptanceCriterionInput(description=d) for d in (acceptance_criteria or [])
                ],
            ),
            timeout=_CALL_TIMEOUT_S,
        )
        return _task_to_dict(resp.task)


async def list_tasks(board_activity_id: str) -> list[dict]:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = board_pb2_grpc.TaskServiceStub(channel)
        resp = await stub.ListTasks(
            board_pb2.ListTasksRequest(board_activity_id=board_activity_id), timeout=_CALL_TIMEOUT_S
        )
        return [_task_to_dict(t) for t in resp.tasks]


async def update_task(*, task_id: str, title: str, done: bool, position: int = 0) -> dict:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = board_pb2_grpc.TaskServiceStub(channel)
        resp = await stub.UpdateTask(
            board_pb2.UpdateTaskRequest(id=task_id, title=title, done=done, position=position),
            timeout=_CALL_TIMEOUT_S,
        )
        return _task_to_dict(resp.task)
