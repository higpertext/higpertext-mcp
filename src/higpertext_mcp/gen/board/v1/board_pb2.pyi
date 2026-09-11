import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Priority(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PRIORITY_UNSPECIFIED: _ClassVar[Priority]
    LOW: _ClassVar[Priority]
    MEDIUM: _ClassVar[Priority]
    HIGH: _ClassVar[Priority]
    CRITICAL: _ClassVar[Priority]
PRIORITY_UNSPECIFIED: Priority
LOW: Priority
MEDIUM: Priority
HIGH: Priority
CRITICAL: Priority

class WorkItemType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    WORK_ITEM_TYPE_UNSPECIFIED: _ClassVar[WorkItemType]
    ROADMAP: _ClassVar[WorkItemType]
    EPIC: _ClassVar[WorkItemType]
    FEATURE: _ClassVar[WorkItemType]
    STORY: _ClassVar[WorkItemType]
    BUG: _ClassVar[WorkItemType]
    ISSUE: _ClassVar[WorkItemType]
WORK_ITEM_TYPE_UNSPECIFIED: WorkItemType
ROADMAP: WorkItemType
EPIC: WorkItemType
FEATURE: WorkItemType
STORY: WorkItemType
BUG: WorkItemType
ISSUE: WorkItemType

class Board(_message.Message):
    __slots__ = ("id", "name", "description", "project_id", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PROJECT_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    description: str
    project_id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., project_id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CreateBoardRequest(_message.Message):
    __slots__ = ("name", "description", "project_id")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PROJECT_ID_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    project_id: str
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., project_id: _Optional[str] = ...) -> None: ...

class CreateBoardResponse(_message.Message):
    __slots__ = ("board",)
    BOARD_FIELD_NUMBER: _ClassVar[int]
    board: Board
    def __init__(self, board: _Optional[_Union[Board, _Mapping]] = ...) -> None: ...

class GetBoardRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetBoardResponse(_message.Message):
    __slots__ = ("board",)
    BOARD_FIELD_NUMBER: _ClassVar[int]
    board: Board
    def __init__(self, board: _Optional[_Union[Board, _Mapping]] = ...) -> None: ...

class ListBoardsRequest(_message.Message):
    __slots__ = ("project_id",)
    PROJECT_ID_FIELD_NUMBER: _ClassVar[int]
    project_id: str
    def __init__(self, project_id: _Optional[str] = ...) -> None: ...

class ListBoardsResponse(_message.Message):
    __slots__ = ("boards",)
    BOARDS_FIELD_NUMBER: _ClassVar[int]
    boards: _containers.RepeatedCompositeFieldContainer[Board]
    def __init__(self, boards: _Optional[_Iterable[_Union[Board, _Mapping]]] = ...) -> None: ...

class DeleteBoardRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ResolveBoardRequest(_message.Message):
    __slots__ = ("project_id", "name")
    PROJECT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    project_id: str
    name: str
    def __init__(self, project_id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class ResolveBoardResponse(_message.Message):
    __slots__ = ("board",)
    BOARD_FIELD_NUMBER: _ClassVar[int]
    board: Board
    def __init__(self, board: _Optional[_Union[Board, _Mapping]] = ...) -> None: ...

class Column(_message.Message):
    __slots__ = ("id", "board_id", "name", "position", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    board_id: str
    name: str
    position: int
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., board_id: _Optional[str] = ..., name: _Optional[str] = ..., position: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CreateColumnRequest(_message.Message):
    __slots__ = ("board_id", "name", "position")
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    name: str
    position: int
    def __init__(self, board_id: _Optional[str] = ..., name: _Optional[str] = ..., position: _Optional[int] = ...) -> None: ...

class CreateColumnResponse(_message.Message):
    __slots__ = ("column",)
    COLUMN_FIELD_NUMBER: _ClassVar[int]
    column: Column
    def __init__(self, column: _Optional[_Union[Column, _Mapping]] = ...) -> None: ...

class ListColumnsRequest(_message.Message):
    __slots__ = ("board_id",)
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    def __init__(self, board_id: _Optional[str] = ...) -> None: ...

class ListColumnsResponse(_message.Message):
    __slots__ = ("columns",)
    COLUMNS_FIELD_NUMBER: _ClassVar[int]
    columns: _containers.RepeatedCompositeFieldContainer[Column]
    def __init__(self, columns: _Optional[_Iterable[_Union[Column, _Mapping]]] = ...) -> None: ...

class DeleteColumnRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ColumnPosition(_message.Message):
    __slots__ = ("id", "position")
    ID_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    id: str
    position: int
    def __init__(self, id: _Optional[str] = ..., position: _Optional[int] = ...) -> None: ...

class ReorderColumnsRequest(_message.Message):
    __slots__ = ("board_id", "columns")
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    COLUMNS_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    columns: _containers.RepeatedCompositeFieldContainer[ColumnPosition]
    def __init__(self, board_id: _Optional[str] = ..., columns: _Optional[_Iterable[_Union[ColumnPosition, _Mapping]]] = ...) -> None: ...

class ReorderColumnsResponse(_message.Message):
    __slots__ = ("columns",)
    COLUMNS_FIELD_NUMBER: _ClassVar[int]
    columns: _containers.RepeatedCompositeFieldContainer[Column]
    def __init__(self, columns: _Optional[_Iterable[_Union[Column, _Mapping]]] = ...) -> None: ...

class BoardActivity(_message.Message):
    __slots__ = ("id", "board_id", "column_id", "title", "description", "assignee_user_id", "priority", "tags", "position", "created_at", "updated_at", "closed_at", "type", "parent_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    COLUMN_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ASSIGNEE_USER_ID_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    CLOSED_AT_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    board_id: str
    column_id: str
    title: str
    description: str
    assignee_user_id: str
    priority: Priority
    tags: _containers.RepeatedScalarFieldContainer[str]
    position: int
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    closed_at: _timestamp_pb2.Timestamp
    type: WorkItemType
    parent_id: str
    def __init__(self, id: _Optional[str] = ..., board_id: _Optional[str] = ..., column_id: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., assignee_user_id: _Optional[str] = ..., priority: _Optional[_Union[Priority, str]] = ..., tags: _Optional[_Iterable[str]] = ..., position: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., closed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., type: _Optional[_Union[WorkItemType, str]] = ..., parent_id: _Optional[str] = ...) -> None: ...

class CreateActivityRequest(_message.Message):
    __slots__ = ("board_id", "column_id", "title", "description", "assignee_user_id", "priority", "tags", "type", "parent_id")
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    COLUMN_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ASSIGNEE_USER_ID_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    column_id: str
    title: str
    description: str
    assignee_user_id: str
    priority: Priority
    tags: _containers.RepeatedScalarFieldContainer[str]
    type: WorkItemType
    parent_id: str
    def __init__(self, board_id: _Optional[str] = ..., column_id: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., assignee_user_id: _Optional[str] = ..., priority: _Optional[_Union[Priority, str]] = ..., tags: _Optional[_Iterable[str]] = ..., type: _Optional[_Union[WorkItemType, str]] = ..., parent_id: _Optional[str] = ...) -> None: ...

class CreateActivityResponse(_message.Message):
    __slots__ = ("activity",)
    ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    activity: BoardActivity
    def __init__(self, activity: _Optional[_Union[BoardActivity, _Mapping]] = ...) -> None: ...

class GetActivityRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetActivityResponse(_message.Message):
    __slots__ = ("activity",)
    ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    activity: BoardActivity
    def __init__(self, activity: _Optional[_Union[BoardActivity, _Mapping]] = ...) -> None: ...

class ListActivitiesRequest(_message.Message):
    __slots__ = ("board_id", "column_id")
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    COLUMN_ID_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    column_id: str
    def __init__(self, board_id: _Optional[str] = ..., column_id: _Optional[str] = ...) -> None: ...

class ListActivitiesResponse(_message.Message):
    __slots__ = ("activities",)
    ACTIVITIES_FIELD_NUMBER: _ClassVar[int]
    activities: _containers.RepeatedCompositeFieldContainer[BoardActivity]
    def __init__(self, activities: _Optional[_Iterable[_Union[BoardActivity, _Mapping]]] = ...) -> None: ...

class UpdateActivityRequest(_message.Message):
    __slots__ = ("id", "title", "description", "assignee_user_id", "priority", "tags")
    ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ASSIGNEE_USER_ID_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    id: str
    title: str
    description: str
    assignee_user_id: str
    priority: Priority
    tags: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, id: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., assignee_user_id: _Optional[str] = ..., priority: _Optional[_Union[Priority, str]] = ..., tags: _Optional[_Iterable[str]] = ...) -> None: ...

class UpdateActivityResponse(_message.Message):
    __slots__ = ("activity",)
    ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    activity: BoardActivity
    def __init__(self, activity: _Optional[_Union[BoardActivity, _Mapping]] = ...) -> None: ...

class DeleteActivityRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class MoveActivityRequest(_message.Message):
    __slots__ = ("id", "target_column_id", "position")
    ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_COLUMN_ID_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    id: str
    target_column_id: str
    position: int
    def __init__(self, id: _Optional[str] = ..., target_column_id: _Optional[str] = ..., position: _Optional[int] = ...) -> None: ...

class MoveActivityResponse(_message.Message):
    __slots__ = ("activity",)
    ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    activity: BoardActivity
    def __init__(self, activity: _Optional[_Union[BoardActivity, _Mapping]] = ...) -> None: ...

class Task(_message.Message):
    __slots__ = ("id", "board_activity_id", "title", "done", "position", "acceptance_criteria", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    BOARD_ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    ACCEPTANCE_CRITERIA_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    board_activity_id: str
    title: str
    done: bool
    position: int
    acceptance_criteria: _containers.RepeatedCompositeFieldContainer[AcceptanceCriterion]
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., board_activity_id: _Optional[str] = ..., title: _Optional[str] = ..., done: _Optional[bool] = ..., position: _Optional[int] = ..., acceptance_criteria: _Optional[_Iterable[_Union[AcceptanceCriterion, _Mapping]]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class AcceptanceCriterion(_message.Message):
    __slots__ = ("id", "task_id", "description", "done", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    task_id: str
    description: str
    done: bool
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., task_id: _Optional[str] = ..., description: _Optional[str] = ..., done: _Optional[bool] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class AcceptanceCriterionInput(_message.Message):
    __slots__ = ("description",)
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    description: str
    def __init__(self, description: _Optional[str] = ...) -> None: ...

class CreateTaskRequest(_message.Message):
    __slots__ = ("board_activity_id", "title", "acceptance_criteria")
    BOARD_ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    ACCEPTANCE_CRITERIA_FIELD_NUMBER: _ClassVar[int]
    board_activity_id: str
    title: str
    acceptance_criteria: _containers.RepeatedCompositeFieldContainer[AcceptanceCriterionInput]
    def __init__(self, board_activity_id: _Optional[str] = ..., title: _Optional[str] = ..., acceptance_criteria: _Optional[_Iterable[_Union[AcceptanceCriterionInput, _Mapping]]] = ...) -> None: ...

class CreateTaskResponse(_message.Message):
    __slots__ = ("task",)
    TASK_FIELD_NUMBER: _ClassVar[int]
    task: Task
    def __init__(self, task: _Optional[_Union[Task, _Mapping]] = ...) -> None: ...

class GetTaskRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetTaskResponse(_message.Message):
    __slots__ = ("task",)
    TASK_FIELD_NUMBER: _ClassVar[int]
    task: Task
    def __init__(self, task: _Optional[_Union[Task, _Mapping]] = ...) -> None: ...

class ListTasksRequest(_message.Message):
    __slots__ = ("board_activity_id",)
    BOARD_ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    board_activity_id: str
    def __init__(self, board_activity_id: _Optional[str] = ...) -> None: ...

class ListTasksResponse(_message.Message):
    __slots__ = ("tasks",)
    TASKS_FIELD_NUMBER: _ClassVar[int]
    tasks: _containers.RepeatedCompositeFieldContainer[Task]
    def __init__(self, tasks: _Optional[_Iterable[_Union[Task, _Mapping]]] = ...) -> None: ...

class UpdateTaskRequest(_message.Message):
    __slots__ = ("id", "title", "done", "position")
    ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    id: str
    title: str
    done: bool
    position: int
    def __init__(self, id: _Optional[str] = ..., title: _Optional[str] = ..., done: _Optional[bool] = ..., position: _Optional[int] = ...) -> None: ...

class UpdateTaskResponse(_message.Message):
    __slots__ = ("task",)
    TASK_FIELD_NUMBER: _ClassVar[int]
    task: Task
    def __init__(self, task: _Optional[_Union[Task, _Mapping]] = ...) -> None: ...

class DeleteTaskRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...
