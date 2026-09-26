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

class WorkItemType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    WORK_ITEM_TYPE_UNSPECIFIED: _ClassVar[WorkItemType]
    ROADMAP: _ClassVar[WorkItemType]
    EPIC: _ClassVar[WorkItemType]
    FEATURE: _ClassVar[WorkItemType]
    STORY: _ClassVar[WorkItemType]
    BUG: _ClassVar[WorkItemType]
    ISSUE: _ClassVar[WorkItemType]

class ScenarioKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SCENARIO_KIND_UNSPECIFIED: _ClassVar[ScenarioKind]
    SCENARIO_HAPPY: _ClassVar[ScenarioKind]
    SCENARIO_NEGATIVE: _ClassVar[ScenarioKind]
    SCENARIO_BOUNDARY: _ClassVar[ScenarioKind]
    SCENARIO_ERROR: _ClassVar[ScenarioKind]

class VerificationState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    VERIFICATION_STATE_UNSPECIFIED: _ClassVar[VerificationState]
    VERIFICATION_DRAFT: _ClassVar[VerificationState]
    VERIFICATION_FROZEN: _ClassVar[VerificationState]
    VERIFICATION_VERIFIED: _ClassVar[VerificationState]
    VERIFICATION_FAILED: _ClassVar[VerificationState]

class VerificationPhase(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    VERIFICATION_PHASE_UNSPECIFIED: _ClassVar[VerificationPhase]
    PHASE_BASE: _ClassVar[VerificationPhase]
    PHASE_HEAD: _ClassVar[VerificationPhase]
PRIORITY_UNSPECIFIED: Priority
LOW: Priority
MEDIUM: Priority
HIGH: Priority
CRITICAL: Priority
WORK_ITEM_TYPE_UNSPECIFIED: WorkItemType
ROADMAP: WorkItemType
EPIC: WorkItemType
FEATURE: WorkItemType
STORY: WorkItemType
BUG: WorkItemType
ISSUE: WorkItemType
SCENARIO_KIND_UNSPECIFIED: ScenarioKind
SCENARIO_HAPPY: ScenarioKind
SCENARIO_NEGATIVE: ScenarioKind
SCENARIO_BOUNDARY: ScenarioKind
SCENARIO_ERROR: ScenarioKind
VERIFICATION_STATE_UNSPECIFIED: VerificationState
VERIFICATION_DRAFT: VerificationState
VERIFICATION_FROZEN: VerificationState
VERIFICATION_VERIFIED: VerificationState
VERIFICATION_FAILED: VerificationState
VERIFICATION_PHASE_UNSPECIFIED: VerificationPhase
PHASE_BASE: VerificationPhase
PHASE_HEAD: VerificationPhase

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

class UpdateBoardRequest(_message.Message):
    __slots__ = ("id", "name", "description")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    description: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class UpdateBoardResponse(_message.Message):
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

class BoardComment(_message.Message):
    __slots__ = ("id", "board_activity_id", "text", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    BOARD_ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    board_activity_id: str
    text: str
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., board_activity_id: _Optional[str] = ..., text: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

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
    __slots__ = ("id", "title", "description", "assignee_user_id", "priority", "tags", "type")
    ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ASSIGNEE_USER_ID_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    id: str
    title: str
    description: str
    assignee_user_id: str
    priority: Priority
    tags: _containers.RepeatedScalarFieldContainer[str]
    type: WorkItemType
    def __init__(self, id: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., assignee_user_id: _Optional[str] = ..., priority: _Optional[_Union[Priority, str]] = ..., tags: _Optional[_Iterable[str]] = ..., type: _Optional[_Union[WorkItemType, str]] = ...) -> None: ...

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

class CreateActivityCommentRequest(_message.Message):
    __slots__ = ("board_activity_id", "text")
    BOARD_ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    board_activity_id: str
    text: str
    def __init__(self, board_activity_id: _Optional[str] = ..., text: _Optional[str] = ...) -> None: ...

class CreateActivityCommentResponse(_message.Message):
    __slots__ = ("comment",)
    COMMENT_FIELD_NUMBER: _ClassVar[int]
    comment: BoardComment
    def __init__(self, comment: _Optional[_Union[BoardComment, _Mapping]] = ...) -> None: ...

class ListActivityCommentsRequest(_message.Message):
    __slots__ = ("board_activity_id",)
    BOARD_ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    board_activity_id: str
    def __init__(self, board_activity_id: _Optional[str] = ...) -> None: ...

class ListActivityCommentsResponse(_message.Message):
    __slots__ = ("comments",)
    COMMENTS_FIELD_NUMBER: _ClassVar[int]
    comments: _containers.RepeatedCompositeFieldContainer[BoardComment]
    def __init__(self, comments: _Optional[_Iterable[_Union[BoardComment, _Mapping]]] = ...) -> None: ...

class Task(_message.Message):
    __slots__ = ("id", "board_activity_id", "title", "done", "position", "acceptance_criteria", "created_at", "updated_at", "verification")
    ID_FIELD_NUMBER: _ClassVar[int]
    BOARD_ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    ACCEPTANCE_CRITERIA_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    VERIFICATION_FIELD_NUMBER: _ClassVar[int]
    id: str
    board_activity_id: str
    title: str
    done: bool
    position: int
    acceptance_criteria: _containers.RepeatedCompositeFieldContainer[AcceptanceCriterion]
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    verification: TaskVerification
    def __init__(self, id: _Optional[str] = ..., board_activity_id: _Optional[str] = ..., title: _Optional[str] = ..., done: _Optional[bool] = ..., position: _Optional[int] = ..., acceptance_criteria: _Optional[_Iterable[_Union[AcceptanceCriterion, _Mapping]]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., verification: _Optional[_Union[TaskVerification, _Mapping]] = ...) -> None: ...

class AcceptanceCriterion(_message.Message):
    __slots__ = ("id", "task_id", "description", "done", "created_at", "scenarios")
    ID_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    SCENARIOS_FIELD_NUMBER: _ClassVar[int]
    id: str
    task_id: str
    description: str
    done: bool
    created_at: _timestamp_pb2.Timestamp
    scenarios: _containers.RepeatedCompositeFieldContainer[VerificationScenario]
    def __init__(self, id: _Optional[str] = ..., task_id: _Optional[str] = ..., description: _Optional[str] = ..., done: _Optional[bool] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., scenarios: _Optional[_Iterable[_Union[VerificationScenario, _Mapping]]] = ...) -> None: ...

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

class VerificationStep(_message.Message):
    __slots__ = ("name", "command", "expect_exit_code", "output_contains", "output_not_contains", "output_regex", "timeout_seconds")
    NAME_FIELD_NUMBER: _ClassVar[int]
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    EXPECT_EXIT_CODE_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_CONTAINS_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_NOT_CONTAINS_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_REGEX_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_SECONDS_FIELD_NUMBER: _ClassVar[int]
    name: str
    command: str
    expect_exit_code: int
    output_contains: _containers.RepeatedScalarFieldContainer[str]
    output_not_contains: _containers.RepeatedScalarFieldContainer[str]
    output_regex: str
    timeout_seconds: int
    def __init__(self, name: _Optional[str] = ..., command: _Optional[str] = ..., expect_exit_code: _Optional[int] = ..., output_contains: _Optional[_Iterable[str]] = ..., output_not_contains: _Optional[_Iterable[str]] = ..., output_regex: _Optional[str] = ..., timeout_seconds: _Optional[int] = ...) -> None: ...

class VerificationScenario(_message.Message):
    __slots__ = ("id", "task_id", "criterion_id", "kind", "title", "regression", "steps", "author", "position", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    CRITERION_ID_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    REGRESSION_FIELD_NUMBER: _ClassVar[int]
    STEPS_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    task_id: str
    criterion_id: str
    kind: ScenarioKind
    title: str
    regression: bool
    steps: _containers.RepeatedCompositeFieldContainer[VerificationStep]
    author: str
    position: int
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., task_id: _Optional[str] = ..., criterion_id: _Optional[str] = ..., kind: _Optional[_Union[ScenarioKind, str]] = ..., title: _Optional[str] = ..., regression: _Optional[bool] = ..., steps: _Optional[_Iterable[_Union[VerificationStep, _Mapping]]] = ..., author: _Optional[str] = ..., position: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class TaskVerification(_message.Message):
    __slots__ = ("state", "spec_hash", "base_commit", "implementer", "frozen_at", "verified_commit", "verified_at")
    STATE_FIELD_NUMBER: _ClassVar[int]
    SPEC_HASH_FIELD_NUMBER: _ClassVar[int]
    BASE_COMMIT_FIELD_NUMBER: _ClassVar[int]
    IMPLEMENTER_FIELD_NUMBER: _ClassVar[int]
    FROZEN_AT_FIELD_NUMBER: _ClassVar[int]
    VERIFIED_COMMIT_FIELD_NUMBER: _ClassVar[int]
    VERIFIED_AT_FIELD_NUMBER: _ClassVar[int]
    state: VerificationState
    spec_hash: str
    base_commit: str
    implementer: str
    frozen_at: _timestamp_pb2.Timestamp
    verified_commit: str
    verified_at: _timestamp_pb2.Timestamp
    def __init__(self, state: _Optional[_Union[VerificationState, str]] = ..., spec_hash: _Optional[str] = ..., base_commit: _Optional[str] = ..., implementer: _Optional[str] = ..., frozen_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., verified_commit: _Optional[str] = ..., verified_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class VerificationScenarioInput(_message.Message):
    __slots__ = ("criterion_id", "kind", "title", "regression", "steps")
    CRITERION_ID_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    REGRESSION_FIELD_NUMBER: _ClassVar[int]
    STEPS_FIELD_NUMBER: _ClassVar[int]
    criterion_id: str
    kind: ScenarioKind
    title: str
    regression: bool
    steps: _containers.RepeatedCompositeFieldContainer[VerificationStep]
    def __init__(self, criterion_id: _Optional[str] = ..., kind: _Optional[_Union[ScenarioKind, str]] = ..., title: _Optional[str] = ..., regression: _Optional[bool] = ..., steps: _Optional[_Iterable[_Union[VerificationStep, _Mapping]]] = ...) -> None: ...

class ProposeScenariosRequest(_message.Message):
    __slots__ = ("task_id", "author", "scenarios", "dry_run")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    SCENARIOS_FIELD_NUMBER: _ClassVar[int]
    DRY_RUN_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    author: str
    scenarios: _containers.RepeatedCompositeFieldContainer[VerificationScenarioInput]
    dry_run: bool
    def __init__(self, task_id: _Optional[str] = ..., author: _Optional[str] = ..., scenarios: _Optional[_Iterable[_Union[VerificationScenarioInput, _Mapping]]] = ..., dry_run: _Optional[bool] = ...) -> None: ...

class ProposeScenariosResponse(_message.Message):
    __slots__ = ("task", "spec_hash")
    TASK_FIELD_NUMBER: _ClassVar[int]
    SPEC_HASH_FIELD_NUMBER: _ClassVar[int]
    task: Task
    spec_hash: str
    def __init__(self, task: _Optional[_Union[Task, _Mapping]] = ..., spec_hash: _Optional[str] = ...) -> None: ...

class FreezeSpecRequest(_message.Message):
    __slots__ = ("task_id", "base_commit", "implementer")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    BASE_COMMIT_FIELD_NUMBER: _ClassVar[int]
    IMPLEMENTER_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    base_commit: str
    implementer: str
    def __init__(self, task_id: _Optional[str] = ..., base_commit: _Optional[str] = ..., implementer: _Optional[str] = ...) -> None: ...

class FreezeSpecResponse(_message.Message):
    __slots__ = ("task",)
    TASK_FIELD_NUMBER: _ClassVar[int]
    task: Task
    def __init__(self, task: _Optional[_Union[Task, _Mapping]] = ...) -> None: ...

class UnfreezeSpecRequest(_message.Message):
    __slots__ = ("task_id", "actor", "reason")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    ACTOR_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    actor: str
    reason: str
    def __init__(self, task_id: _Optional[str] = ..., actor: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class UnfreezeSpecResponse(_message.Message):
    __slots__ = ("task",)
    TASK_FIELD_NUMBER: _ClassVar[int]
    task: Task
    def __init__(self, task: _Optional[_Union[Task, _Mapping]] = ...) -> None: ...

class StepEvidence(_message.Message):
    __slots__ = ("scenario_id", "phase", "step_index", "exit_code", "output", "output_truncated", "duration_ms")
    SCENARIO_ID_FIELD_NUMBER: _ClassVar[int]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    STEP_INDEX_FIELD_NUMBER: _ClassVar[int]
    EXIT_CODE_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    scenario_id: str
    phase: VerificationPhase
    step_index: int
    exit_code: int
    output: str
    output_truncated: bool
    duration_ms: int
    def __init__(self, scenario_id: _Optional[str] = ..., phase: _Optional[_Union[VerificationPhase, str]] = ..., step_index: _Optional[int] = ..., exit_code: _Optional[int] = ..., output: _Optional[str] = ..., output_truncated: _Optional[bool] = ..., duration_ms: _Optional[int] = ...) -> None: ...

class StepResult(_message.Message):
    __slots__ = ("scenario_id", "phase", "step_index", "exit_code", "passed", "detail", "output_sha256", "duration_ms")
    SCENARIO_ID_FIELD_NUMBER: _ClassVar[int]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    STEP_INDEX_FIELD_NUMBER: _ClassVar[int]
    EXIT_CODE_FIELD_NUMBER: _ClassVar[int]
    PASSED_FIELD_NUMBER: _ClassVar[int]
    DETAIL_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_SHA256_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    scenario_id: str
    phase: VerificationPhase
    step_index: int
    exit_code: int
    passed: bool
    detail: str
    output_sha256: str
    duration_ms: int
    def __init__(self, scenario_id: _Optional[str] = ..., phase: _Optional[_Union[VerificationPhase, str]] = ..., step_index: _Optional[int] = ..., exit_code: _Optional[int] = ..., passed: _Optional[bool] = ..., detail: _Optional[str] = ..., output_sha256: _Optional[str] = ..., duration_ms: _Optional[int] = ...) -> None: ...

class VerificationRun(_message.Message):
    __slots__ = ("id", "task_id", "event", "spec_hash", "base_commit", "head_commit", "actor", "passed", "reasons", "results", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    SPEC_HASH_FIELD_NUMBER: _ClassVar[int]
    BASE_COMMIT_FIELD_NUMBER: _ClassVar[int]
    HEAD_COMMIT_FIELD_NUMBER: _ClassVar[int]
    ACTOR_FIELD_NUMBER: _ClassVar[int]
    PASSED_FIELD_NUMBER: _ClassVar[int]
    REASONS_FIELD_NUMBER: _ClassVar[int]
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    task_id: str
    event: str
    spec_hash: str
    base_commit: str
    head_commit: str
    actor: str
    passed: bool
    reasons: _containers.RepeatedScalarFieldContainer[str]
    results: _containers.RepeatedCompositeFieldContainer[StepResult]
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., task_id: _Optional[str] = ..., event: _Optional[str] = ..., spec_hash: _Optional[str] = ..., base_commit: _Optional[str] = ..., head_commit: _Optional[str] = ..., actor: _Optional[str] = ..., passed: _Optional[bool] = ..., reasons: _Optional[_Iterable[str]] = ..., results: _Optional[_Iterable[_Union[StepResult, _Mapping]]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class RecordVerificationRequest(_message.Message):
    __slots__ = ("task_id", "spec_hash", "base_commit", "head_commit", "runner", "evidence")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    SPEC_HASH_FIELD_NUMBER: _ClassVar[int]
    BASE_COMMIT_FIELD_NUMBER: _ClassVar[int]
    HEAD_COMMIT_FIELD_NUMBER: _ClassVar[int]
    RUNNER_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    spec_hash: str
    base_commit: str
    head_commit: str
    runner: str
    evidence: _containers.RepeatedCompositeFieldContainer[StepEvidence]
    def __init__(self, task_id: _Optional[str] = ..., spec_hash: _Optional[str] = ..., base_commit: _Optional[str] = ..., head_commit: _Optional[str] = ..., runner: _Optional[str] = ..., evidence: _Optional[_Iterable[_Union[StepEvidence, _Mapping]]] = ...) -> None: ...

class RecordVerificationResponse(_message.Message):
    __slots__ = ("run", "task")
    RUN_FIELD_NUMBER: _ClassVar[int]
    TASK_FIELD_NUMBER: _ClassVar[int]
    run: VerificationRun
    task: Task
    def __init__(self, run: _Optional[_Union[VerificationRun, _Mapping]] = ..., task: _Optional[_Union[Task, _Mapping]] = ...) -> None: ...

class ListVerificationRunsRequest(_message.Message):
    __slots__ = ("task_id", "limit")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    limit: int
    def __init__(self, task_id: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class ListVerificationRunsResponse(_message.Message):
    __slots__ = ("runs",)
    RUNS_FIELD_NUMBER: _ClassVar[int]
    runs: _containers.RepeatedCompositeFieldContainer[VerificationRun]
    def __init__(self, runs: _Optional[_Iterable[_Union[VerificationRun, _Mapping]]] = ...) -> None: ...

class GetActivityGateRequest(_message.Message):
    __slots__ = ("activity_id",)
    ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    activity_id: str
    def __init__(self, activity_id: _Optional[str] = ...) -> None: ...

class GetActivityGateResponse(_message.Message):
    __slots__ = ("ready", "blocking")
    READY_FIELD_NUMBER: _ClassVar[int]
    BLOCKING_FIELD_NUMBER: _ClassVar[int]
    ready: bool
    blocking: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, ready: _Optional[bool] = ..., blocking: _Optional[_Iterable[str]] = ...) -> None: ...
