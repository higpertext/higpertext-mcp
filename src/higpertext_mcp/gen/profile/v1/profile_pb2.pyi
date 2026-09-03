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

class Severity(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SEVERITY_UNSPECIFIED: _ClassVar[Severity]
    LOW: _ClassVar[Severity]
    MEDIUM: _ClassVar[Severity]
    HIGH: _ClassVar[Severity]
    CRITICAL: _ClassVar[Severity]

class Scope(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SCOPE_UNSPECIFIED: _ClassVar[Scope]
    COMMIT: _ClassVar[Scope]
    PR: _ClassVar[Scope]
    DEPLOY: _ClassVar[Scope]
    ANY: _ClassVar[Scope]
SEVERITY_UNSPECIFIED: Severity
LOW: Severity
MEDIUM: Severity
HIGH: Severity
CRITICAL: Severity
SCOPE_UNSPECIFIED: Scope
COMMIT: Scope
PR: Scope
DEPLOY: Scope
ANY: Scope

class Profile(_message.Message):
    __slots__ = ("id", "name", "description", "system_prompt", "capabilities", "subprofiles", "rules", "hooks_global", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_PROMPT_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    SUBPROFILES_FIELD_NUMBER: _ClassVar[int]
    RULES_FIELD_NUMBER: _ClassVar[int]
    HOOKS_GLOBAL_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    description: str
    system_prompt: str
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    subprofiles: _containers.RepeatedScalarFieldContainer[str]
    rules: _containers.RepeatedScalarFieldContainer[str]
    hooks_global: _containers.RepeatedScalarFieldContainer[str]
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., system_prompt: _Optional[str] = ..., capabilities: _Optional[_Iterable[str]] = ..., subprofiles: _Optional[_Iterable[str]] = ..., rules: _Optional[_Iterable[str]] = ..., hooks_global: _Optional[_Iterable[str]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Parameter(_message.Message):
    __slots__ = ("name", "type", "required", "description")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: str
    required: bool
    description: str
    def __init__(self, name: _Optional[str] = ..., type: _Optional[str] = ..., required: _Optional[bool] = ..., description: _Optional[str] = ...) -> None: ...

class Contract(_message.Message):
    __slots__ = ("rules", "success_pattern")
    RULES_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_PATTERN_FIELD_NUMBER: _ClassVar[int]
    rules: _containers.RepeatedScalarFieldContainer[str]
    success_pattern: str
    def __init__(self, rules: _Optional[_Iterable[str]] = ..., success_pattern: _Optional[str] = ...) -> None: ...

class Capability(_message.Message):
    __slots__ = ("id", "version", "name", "description", "entrypoint", "language", "parameters", "requires_pat", "hook_task_id", "contract", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ENTRYPOINT_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    REQUIRES_PAT_FIELD_NUMBER: _ClassVar[int]
    HOOK_TASK_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    version: str
    name: str
    description: str
    entrypoint: str
    language: str
    parameters: _containers.RepeatedCompositeFieldContainer[Parameter]
    requires_pat: bool
    hook_task_id: str
    contract: Contract
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., version: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., entrypoint: _Optional[str] = ..., language: _Optional[str] = ..., parameters: _Optional[_Iterable[_Union[Parameter, _Mapping]]] = ..., requires_pat: _Optional[bool] = ..., hook_task_id: _Optional[str] = ..., contract: _Optional[_Union[Contract, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GovernanceRule(_message.Message):
    __slots__ = ("id", "description", "severity", "scopes", "automated", "capability", "source", "numeric_threshold", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    SCOPES_FIELD_NUMBER: _ClassVar[int]
    AUTOMATED_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    NUMERIC_THRESHOLD_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    description: str
    severity: Severity
    scopes: _containers.RepeatedScalarFieldContainer[Scope]
    automated: bool
    capability: str
    source: str
    numeric_threshold: float
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., description: _Optional[str] = ..., severity: _Optional[_Union[Severity, str]] = ..., scopes: _Optional[_Iterable[_Union[Scope, str]]] = ..., automated: _Optional[bool] = ..., capability: _Optional[str] = ..., source: _Optional[str] = ..., numeric_threshold: _Optional[float] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GovernanceException(_message.Message):
    __slots__ = ("id", "rule_id", "reason", "approver", "profile", "expires", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    RULE_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    APPROVER_FIELD_NUMBER: _ClassVar[int]
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    rule_id: str
    reason: str
    approver: str
    profile: str
    expires: str
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., rule_id: _Optional[str] = ..., reason: _Optional[str] = ..., approver: _Optional[str] = ..., profile: _Optional[str] = ..., expires: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Activity(_message.Message):
    __slots__ = ("id", "capability_id", "profile", "status", "summary", "tags", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_ID_FIELD_NUMBER: _ClassVar[int]
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    capability_id: str
    profile: str
    status: str
    summary: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., capability_id: _Optional[str] = ..., profile: _Optional[str] = ..., status: _Optional[str] = ..., summary: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CreateProfileRequest(_message.Message):
    __slots__ = ("name", "description", "system_prompt", "capabilities", "subprofiles", "rules", "hooks_global")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_PROMPT_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    SUBPROFILES_FIELD_NUMBER: _ClassVar[int]
    RULES_FIELD_NUMBER: _ClassVar[int]
    HOOKS_GLOBAL_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    system_prompt: str
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    subprofiles: _containers.RepeatedScalarFieldContainer[str]
    rules: _containers.RepeatedScalarFieldContainer[str]
    hooks_global: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., system_prompt: _Optional[str] = ..., capabilities: _Optional[_Iterable[str]] = ..., subprofiles: _Optional[_Iterable[str]] = ..., rules: _Optional[_Iterable[str]] = ..., hooks_global: _Optional[_Iterable[str]] = ...) -> None: ...

class CreateProfileResponse(_message.Message):
    __slots__ = ("profile",)
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    profile: Profile
    def __init__(self, profile: _Optional[_Union[Profile, _Mapping]] = ...) -> None: ...

class GetProfileRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetProfileResponse(_message.Message):
    __slots__ = ("profile",)
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    profile: Profile
    def __init__(self, profile: _Optional[_Union[Profile, _Mapping]] = ...) -> None: ...

class ListProfilesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListProfilesResponse(_message.Message):
    __slots__ = ("profiles",)
    PROFILES_FIELD_NUMBER: _ClassVar[int]
    profiles: _containers.RepeatedCompositeFieldContainer[Profile]
    def __init__(self, profiles: _Optional[_Iterable[_Union[Profile, _Mapping]]] = ...) -> None: ...

class UpdateProfileRequest(_message.Message):
    __slots__ = ("id", "name", "description", "system_prompt", "capabilities", "subprofiles", "rules", "hooks_global")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_PROMPT_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    SUBPROFILES_FIELD_NUMBER: _ClassVar[int]
    RULES_FIELD_NUMBER: _ClassVar[int]
    HOOKS_GLOBAL_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    description: str
    system_prompt: str
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    subprofiles: _containers.RepeatedScalarFieldContainer[str]
    rules: _containers.RepeatedScalarFieldContainer[str]
    hooks_global: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., system_prompt: _Optional[str] = ..., capabilities: _Optional[_Iterable[str]] = ..., subprofiles: _Optional[_Iterable[str]] = ..., rules: _Optional[_Iterable[str]] = ..., hooks_global: _Optional[_Iterable[str]] = ...) -> None: ...

class UpdateProfileResponse(_message.Message):
    __slots__ = ("profile",)
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    profile: Profile
    def __init__(self, profile: _Optional[_Union[Profile, _Mapping]] = ...) -> None: ...

class DeleteProfileRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class CreateCapabilityRequest(_message.Message):
    __slots__ = ("id", "version", "name", "description", "entrypoint", "language", "parameters", "requires_pat", "hook_task_id", "contract")
    ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ENTRYPOINT_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    REQUIRES_PAT_FIELD_NUMBER: _ClassVar[int]
    HOOK_TASK_ID_FIELD_NUMBER: _ClassVar[int]
    CONTRACT_FIELD_NUMBER: _ClassVar[int]
    id: str
    version: str
    name: str
    description: str
    entrypoint: str
    language: str
    parameters: _containers.RepeatedCompositeFieldContainer[Parameter]
    requires_pat: bool
    hook_task_id: str
    contract: Contract
    def __init__(self, id: _Optional[str] = ..., version: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., entrypoint: _Optional[str] = ..., language: _Optional[str] = ..., parameters: _Optional[_Iterable[_Union[Parameter, _Mapping]]] = ..., requires_pat: _Optional[bool] = ..., hook_task_id: _Optional[str] = ..., contract: _Optional[_Union[Contract, _Mapping]] = ...) -> None: ...

class CreateCapabilityResponse(_message.Message):
    __slots__ = ("capability",)
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    capability: Capability
    def __init__(self, capability: _Optional[_Union[Capability, _Mapping]] = ...) -> None: ...

class GetCapabilityRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetCapabilityResponse(_message.Message):
    __slots__ = ("capability",)
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    capability: Capability
    def __init__(self, capability: _Optional[_Union[Capability, _Mapping]] = ...) -> None: ...

class ListCapabilitiesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListCapabilitiesResponse(_message.Message):
    __slots__ = ("capabilities",)
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    capabilities: _containers.RepeatedCompositeFieldContainer[Capability]
    def __init__(self, capabilities: _Optional[_Iterable[_Union[Capability, _Mapping]]] = ...) -> None: ...

class DeleteCapabilityRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class CreateRuleRequest(_message.Message):
    __slots__ = ("id", "description", "severity", "scopes", "automated", "capability", "source", "numeric_threshold")
    ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    SCOPES_FIELD_NUMBER: _ClassVar[int]
    AUTOMATED_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    NUMERIC_THRESHOLD_FIELD_NUMBER: _ClassVar[int]
    id: str
    description: str
    severity: Severity
    scopes: _containers.RepeatedScalarFieldContainer[Scope]
    automated: bool
    capability: str
    source: str
    numeric_threshold: float
    def __init__(self, id: _Optional[str] = ..., description: _Optional[str] = ..., severity: _Optional[_Union[Severity, str]] = ..., scopes: _Optional[_Iterable[_Union[Scope, str]]] = ..., automated: _Optional[bool] = ..., capability: _Optional[str] = ..., source: _Optional[str] = ..., numeric_threshold: _Optional[float] = ...) -> None: ...

class CreateRuleResponse(_message.Message):
    __slots__ = ("rule",)
    RULE_FIELD_NUMBER: _ClassVar[int]
    rule: GovernanceRule
    def __init__(self, rule: _Optional[_Union[GovernanceRule, _Mapping]] = ...) -> None: ...

class ListRulesRequest(_message.Message):
    __slots__ = ("scope",)
    SCOPE_FIELD_NUMBER: _ClassVar[int]
    scope: Scope
    def __init__(self, scope: _Optional[_Union[Scope, str]] = ...) -> None: ...

class ListRulesResponse(_message.Message):
    __slots__ = ("rules",)
    RULES_FIELD_NUMBER: _ClassVar[int]
    rules: _containers.RepeatedCompositeFieldContainer[GovernanceRule]
    def __init__(self, rules: _Optional[_Iterable[_Union[GovernanceRule, _Mapping]]] = ...) -> None: ...

class DeleteRuleRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class CreateExceptionRequest(_message.Message):
    __slots__ = ("rule_id", "reason", "approver", "profile", "expires")
    RULE_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    APPROVER_FIELD_NUMBER: _ClassVar[int]
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_FIELD_NUMBER: _ClassVar[int]
    rule_id: str
    reason: str
    approver: str
    profile: str
    expires: str
    def __init__(self, rule_id: _Optional[str] = ..., reason: _Optional[str] = ..., approver: _Optional[str] = ..., profile: _Optional[str] = ..., expires: _Optional[str] = ...) -> None: ...

class CreateExceptionResponse(_message.Message):
    __slots__ = ("exception",)
    EXCEPTION_FIELD_NUMBER: _ClassVar[int]
    exception: GovernanceException
    def __init__(self, exception: _Optional[_Union[GovernanceException, _Mapping]] = ...) -> None: ...

class ListExceptionsRequest(_message.Message):
    __slots__ = ("profile", "active_only")
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_ONLY_FIELD_NUMBER: _ClassVar[int]
    profile: str
    active_only: bool
    def __init__(self, profile: _Optional[str] = ..., active_only: _Optional[bool] = ...) -> None: ...

class ListExceptionsResponse(_message.Message):
    __slots__ = ("exceptions",)
    EXCEPTIONS_FIELD_NUMBER: _ClassVar[int]
    exceptions: _containers.RepeatedCompositeFieldContainer[GovernanceException]
    def __init__(self, exceptions: _Optional[_Iterable[_Union[GovernanceException, _Mapping]]] = ...) -> None: ...

class DeleteExceptionRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class RecordActivityRequest(_message.Message):
    __slots__ = ("capability_id", "profile", "status", "summary", "tags")
    CAPABILITY_ID_FIELD_NUMBER: _ClassVar[int]
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    capability_id: str
    profile: str
    status: str
    summary: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, capability_id: _Optional[str] = ..., profile: _Optional[str] = ..., status: _Optional[str] = ..., summary: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ...) -> None: ...

class RecordActivityResponse(_message.Message):
    __slots__ = ("activity",)
    ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    activity: Activity
    def __init__(self, activity: _Optional[_Union[Activity, _Mapping]] = ...) -> None: ...

class ListActivitiesRequest(_message.Message):
    __slots__ = ("profile", "limit")
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    profile: str
    limit: int
    def __init__(self, profile: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class ListActivitiesResponse(_message.Message):
    __slots__ = ("activities",)
    ACTIVITIES_FIELD_NUMBER: _ClassVar[int]
    activities: _containers.RepeatedCompositeFieldContainer[Activity]
    def __init__(self, activities: _Optional[_Iterable[_Union[Activity, _Mapping]]] = ...) -> None: ...
