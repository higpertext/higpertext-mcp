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
    __slots__ = ("name", "type", "required", "description", "default")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    REQUIRED_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: str
    required: bool
    description: str
    default: str
    def __init__(self, name: _Optional[str] = ..., type: _Optional[str] = ..., required: _Optional[bool] = ..., description: _Optional[str] = ..., default: _Optional[str] = ...) -> None: ...

class Contract(_message.Message):
    __slots__ = ("rules", "success_pattern", "on_empty")
    RULES_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_PATTERN_FIELD_NUMBER: _ClassVar[int]
    ON_EMPTY_FIELD_NUMBER: _ClassVar[int]
    rules: _containers.RepeatedScalarFieldContainer[str]
    success_pattern: str
    on_empty: str
    def __init__(self, rules: _Optional[_Iterable[str]] = ..., success_pattern: _Optional[str] = ..., on_empty: _Optional[str] = ...) -> None: ...

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

class Skill(_message.Message):
    __slots__ = ("id", "name", "description", "content", "version", "enabled", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    description: str
    content: str
    version: str
    enabled: bool
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., content: _Optional[str] = ..., version: _Optional[str] = ..., enabled: _Optional[bool] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class HookDefinition(_message.Message):
    __slots__ = ("id", "event", "matcher", "script", "description", "timeout", "enabled", "assistants", "profiles", "capability_id", "priority", "source_code", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    MATCHER_FIELD_NUMBER: _ClassVar[int]
    SCRIPT_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    ASSISTANTS_FIELD_NUMBER: _ClassVar[int]
    PROFILES_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_ID_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    SOURCE_CODE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    event: str
    matcher: str
    script: str
    description: str
    timeout: int
    enabled: bool
    assistants: _containers.RepeatedScalarFieldContainer[str]
    profiles: _containers.RepeatedScalarFieldContainer[str]
    capability_id: str
    priority: int
    source_code: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., event: _Optional[str] = ..., matcher: _Optional[str] = ..., script: _Optional[str] = ..., description: _Optional[str] = ..., timeout: _Optional[int] = ..., enabled: _Optional[bool] = ..., assistants: _Optional[_Iterable[str]] = ..., profiles: _Optional[_Iterable[str]] = ..., capability_id: _Optional[str] = ..., priority: _Optional[int] = ..., source_code: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GovernanceRule(_message.Message):
    __slots__ = ("id", "description", "severity", "scopes", "automated", "capability", "source", "numeric_threshold", "created_at", "updated_at", "pattern")
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
    PATTERN_FIELD_NUMBER: _ClassVar[int]
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
    pattern: str
    def __init__(self, id: _Optional[str] = ..., description: _Optional[str] = ..., severity: _Optional[_Union[Severity, str]] = ..., scopes: _Optional[_Iterable[_Union[Scope, str]]] = ..., automated: _Optional[bool] = ..., capability: _Optional[str] = ..., source: _Optional[str] = ..., numeric_threshold: _Optional[float] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., pattern: _Optional[str] = ...) -> None: ...

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

class LearningEvent(_message.Message):
    __slots__ = ("id", "capability_id", "profile", "outcome", "summary", "tags", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_ID_FIELD_NUMBER: _ClassVar[int]
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    capability_id: str
    profile: str
    outcome: str
    summary: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., capability_id: _Optional[str] = ..., profile: _Optional[str] = ..., outcome: _Optional[str] = ..., summary: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class LearningStat(_message.Message):
    __slots__ = ("capability_id", "successes", "failures", "total", "success_rate", "updated_at")
    CAPABILITY_ID_FIELD_NUMBER: _ClassVar[int]
    SUCCESSES_FIELD_NUMBER: _ClassVar[int]
    FAILURES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_RATE_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    capability_id: str
    successes: int
    failures: int
    total: int
    success_rate: float
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, capability_id: _Optional[str] = ..., successes: _Optional[int] = ..., failures: _Optional[int] = ..., total: _Optional[int] = ..., success_rate: _Optional[float] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

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
    __slots__ = ("id", "version", "name", "description", "entrypoint", "language", "parameters", "requires_pat", "hook_task_id", "contract", "source_code", "extra_files")
    class ExtraFilesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
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
    SOURCE_CODE_FIELD_NUMBER: _ClassVar[int]
    EXTRA_FILES_FIELD_NUMBER: _ClassVar[int]
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
    source_code: str
    extra_files: _containers.ScalarMap[str, str]
    def __init__(self, id: _Optional[str] = ..., version: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., entrypoint: _Optional[str] = ..., language: _Optional[str] = ..., parameters: _Optional[_Iterable[_Union[Parameter, _Mapping]]] = ..., requires_pat: _Optional[bool] = ..., hook_task_id: _Optional[str] = ..., contract: _Optional[_Union[Contract, _Mapping]] = ..., source_code: _Optional[str] = ..., extra_files: _Optional[_Mapping[str, str]] = ...) -> None: ...

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

class GetCapabilityScriptRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetCapabilityScriptResponse(_message.Message):
    __slots__ = ("source_code", "language", "extra_files")
    class ExtraFilesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    SOURCE_CODE_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    EXTRA_FILES_FIELD_NUMBER: _ClassVar[int]
    source_code: str
    language: str
    extra_files: _containers.ScalarMap[str, str]
    def __init__(self, source_code: _Optional[str] = ..., language: _Optional[str] = ..., extra_files: _Optional[_Mapping[str, str]] = ...) -> None: ...

class CreateSkillRequest(_message.Message):
    __slots__ = ("id", "name", "description", "content", "version", "enabled")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    description: str
    content: str
    version: str
    enabled: bool
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., content: _Optional[str] = ..., version: _Optional[str] = ..., enabled: _Optional[bool] = ...) -> None: ...

class CreateSkillResponse(_message.Message):
    __slots__ = ("skill",)
    SKILL_FIELD_NUMBER: _ClassVar[int]
    skill: Skill
    def __init__(self, skill: _Optional[_Union[Skill, _Mapping]] = ...) -> None: ...

class GetSkillRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetSkillResponse(_message.Message):
    __slots__ = ("skill",)
    SKILL_FIELD_NUMBER: _ClassVar[int]
    skill: Skill
    def __init__(self, skill: _Optional[_Union[Skill, _Mapping]] = ...) -> None: ...

class ListSkillsRequest(_message.Message):
    __slots__ = ("enabled_only",)
    ENABLED_ONLY_FIELD_NUMBER: _ClassVar[int]
    enabled_only: bool
    def __init__(self, enabled_only: _Optional[bool] = ...) -> None: ...

class ListSkillsResponse(_message.Message):
    __slots__ = ("skills",)
    SKILLS_FIELD_NUMBER: _ClassVar[int]
    skills: _containers.RepeatedCompositeFieldContainer[Skill]
    def __init__(self, skills: _Optional[_Iterable[_Union[Skill, _Mapping]]] = ...) -> None: ...

class UpdateSkillRequest(_message.Message):
    __slots__ = ("id", "name", "description", "content", "version", "enabled")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    description: str
    content: str
    version: str
    enabled: bool
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., content: _Optional[str] = ..., version: _Optional[str] = ..., enabled: _Optional[bool] = ...) -> None: ...

class UpdateSkillResponse(_message.Message):
    __slots__ = ("skill",)
    SKILL_FIELD_NUMBER: _ClassVar[int]
    skill: Skill
    def __init__(self, skill: _Optional[_Union[Skill, _Mapping]] = ...) -> None: ...

class DeleteSkillRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class CreateHookRequest(_message.Message):
    __slots__ = ("id", "event", "matcher", "script", "description", "timeout", "enabled", "assistants", "profiles", "capability_id", "priority", "source_code")
    ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    MATCHER_FIELD_NUMBER: _ClassVar[int]
    SCRIPT_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    ASSISTANTS_FIELD_NUMBER: _ClassVar[int]
    PROFILES_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_ID_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    SOURCE_CODE_FIELD_NUMBER: _ClassVar[int]
    id: str
    event: str
    matcher: str
    script: str
    description: str
    timeout: int
    enabled: bool
    assistants: _containers.RepeatedScalarFieldContainer[str]
    profiles: _containers.RepeatedScalarFieldContainer[str]
    capability_id: str
    priority: int
    source_code: str
    def __init__(self, id: _Optional[str] = ..., event: _Optional[str] = ..., matcher: _Optional[str] = ..., script: _Optional[str] = ..., description: _Optional[str] = ..., timeout: _Optional[int] = ..., enabled: _Optional[bool] = ..., assistants: _Optional[_Iterable[str]] = ..., profiles: _Optional[_Iterable[str]] = ..., capability_id: _Optional[str] = ..., priority: _Optional[int] = ..., source_code: _Optional[str] = ...) -> None: ...

class CreateHookResponse(_message.Message):
    __slots__ = ("hook",)
    HOOK_FIELD_NUMBER: _ClassVar[int]
    hook: HookDefinition
    def __init__(self, hook: _Optional[_Union[HookDefinition, _Mapping]] = ...) -> None: ...

class GetHookRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetHookResponse(_message.Message):
    __slots__ = ("hook",)
    HOOK_FIELD_NUMBER: _ClassVar[int]
    hook: HookDefinition
    def __init__(self, hook: _Optional[_Union[HookDefinition, _Mapping]] = ...) -> None: ...

class ListHooksRequest(_message.Message):
    __slots__ = ("profile", "assistant")
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    ASSISTANT_FIELD_NUMBER: _ClassVar[int]
    profile: str
    assistant: str
    def __init__(self, profile: _Optional[str] = ..., assistant: _Optional[str] = ...) -> None: ...

class ListHooksResponse(_message.Message):
    __slots__ = ("hooks",)
    HOOKS_FIELD_NUMBER: _ClassVar[int]
    hooks: _containers.RepeatedCompositeFieldContainer[HookDefinition]
    def __init__(self, hooks: _Optional[_Iterable[_Union[HookDefinition, _Mapping]]] = ...) -> None: ...

class DeleteHookRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetHookScriptRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetHookScriptResponse(_message.Message):
    __slots__ = ("source_code",)
    SOURCE_CODE_FIELD_NUMBER: _ClassVar[int]
    source_code: str
    def __init__(self, source_code: _Optional[str] = ...) -> None: ...

class SharedHookAssets(_message.Message):
    __slots__ = ("files", "updated_at")
    class FilesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    FILES_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    files: _containers.ScalarMap[str, str]
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, files: _Optional[_Mapping[str, str]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class SetSharedHookAssetsRequest(_message.Message):
    __slots__ = ("files",)
    class FilesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    FILES_FIELD_NUMBER: _ClassVar[int]
    files: _containers.ScalarMap[str, str]
    def __init__(self, files: _Optional[_Mapping[str, str]] = ...) -> None: ...

class SetSharedHookAssetsResponse(_message.Message):
    __slots__ = ("assets",)
    ASSETS_FIELD_NUMBER: _ClassVar[int]
    assets: SharedHookAssets
    def __init__(self, assets: _Optional[_Union[SharedHookAssets, _Mapping]] = ...) -> None: ...

class GetSharedHookAssetsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetSharedHookAssetsResponse(_message.Message):
    __slots__ = ("assets",)
    ASSETS_FIELD_NUMBER: _ClassVar[int]
    assets: SharedHookAssets
    def __init__(self, assets: _Optional[_Union[SharedHookAssets, _Mapping]] = ...) -> None: ...

class CreateRuleRequest(_message.Message):
    __slots__ = ("id", "description", "severity", "scopes", "automated", "capability", "source", "numeric_threshold", "pattern")
    ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    SCOPES_FIELD_NUMBER: _ClassVar[int]
    AUTOMATED_FIELD_NUMBER: _ClassVar[int]
    CAPABILITY_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    NUMERIC_THRESHOLD_FIELD_NUMBER: _ClassVar[int]
    PATTERN_FIELD_NUMBER: _ClassVar[int]
    id: str
    description: str
    severity: Severity
    scopes: _containers.RepeatedScalarFieldContainer[Scope]
    automated: bool
    capability: str
    source: str
    numeric_threshold: float
    pattern: str
    def __init__(self, id: _Optional[str] = ..., description: _Optional[str] = ..., severity: _Optional[_Union[Severity, str]] = ..., scopes: _Optional[_Iterable[_Union[Scope, str]]] = ..., automated: _Optional[bool] = ..., capability: _Optional[str] = ..., source: _Optional[str] = ..., numeric_threshold: _Optional[float] = ..., pattern: _Optional[str] = ...) -> None: ...

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

class RecordLearningRequest(_message.Message):
    __slots__ = ("capability_id", "profile", "outcome", "summary", "tags")
    CAPABILITY_ID_FIELD_NUMBER: _ClassVar[int]
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    capability_id: str
    profile: str
    outcome: str
    summary: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, capability_id: _Optional[str] = ..., profile: _Optional[str] = ..., outcome: _Optional[str] = ..., summary: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ...) -> None: ...

class RecordLearningResponse(_message.Message):
    __slots__ = ("event",)
    EVENT_FIELD_NUMBER: _ClassVar[int]
    event: LearningEvent
    def __init__(self, event: _Optional[_Union[LearningEvent, _Mapping]] = ...) -> None: ...

class ListLearningEventsRequest(_message.Message):
    __slots__ = ("profile", "limit")
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    profile: str
    limit: int
    def __init__(self, profile: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class ListLearningEventsResponse(_message.Message):
    __slots__ = ("events",)
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[LearningEvent]
    def __init__(self, events: _Optional[_Iterable[_Union[LearningEvent, _Mapping]]] = ...) -> None: ...

class GetLearningStatsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetLearningStatsResponse(_message.Message):
    __slots__ = ("stats",)
    STATS_FIELD_NUMBER: _ClassVar[int]
    stats: _containers.RepeatedCompositeFieldContainer[LearningStat]
    def __init__(self, stats: _Optional[_Iterable[_Union[LearningStat, _Mapping]]] = ...) -> None: ...
