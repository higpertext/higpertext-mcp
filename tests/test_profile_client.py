"""Cobertura de profile_client.py con un canal/stub gRPC fake — sin depender
de un profile server real corriendo, mismo criterio que memory.py/test_memory.py
usa para Redis."""

from contextlib import asynccontextmanager

import grpc
import pytest

from higpertext_mcp import profile_client
from higpertext_mcp.gen.learning.v1 import learning_pb2
from higpertext_mcp.gen.profile.v1 import profile_pb2


class _FakeProfileStub:
    def __init__(self, profiles: list[profile_pb2.Profile]) -> None:
        self._profiles = profiles

    async def ListProfiles(self, _request, timeout=None):
        return profile_pb2.ListProfilesResponse(profiles=self._profiles)


class _FakeCapabilityStub:
    def __init__(
        self,
        capabilities: list[profile_pb2.Capability],
        *,
        script: tuple[str, str] | tuple[str, str, dict[str, str]] | None = None,
    ) -> None:
        self._capabilities = capabilities
        self._script = script

    async def ListCapabilities(self, _request, timeout=None):
        return profile_pb2.ListCapabilitiesResponse(capabilities=self._capabilities)

    async def GetCapabilityScript(self, _request, timeout=None):
        if self._script is None:
            raise AssertionError("GetCapabilityScript no esperado en este test")
        source_code, language, *rest = self._script
        extra_files = rest[0] if rest else {}
        return profile_pb2.GetCapabilityScriptResponse(
            source_code=source_code, language=language, extra_files=extra_files
        )


def _caps(*ids: str) -> list[profile_pb2.Capability]:
    return [profile_pb2.Capability(id=cid) for cid in ids]


class _FakeActivityStub:
    def __init__(self) -> None:
        self.recorded: list[profile_pb2.RecordActivityRequest] = []

    async def RecordActivity(self, request, timeout=None):
        self.recorded.append(request)
        return profile_pb2.RecordActivityResponse(activity=profile_pb2.Activity(id="fake-id"))


class _FakeLearningStub:
    def __init__(self) -> None:
        self.recorded: list[learning_pb2.RecordLearningTextRequest] = []

    async def RecordText(self, request, timeout=None):
        self.recorded.append(request)
        return learning_pb2.RecordLearningTextResponse(text=request.text)


def _patch_channel(
    monkeypatch, *, profile_stub=None, capability_stub=None, activity_stub=None, learning_stub=None
):
    @asynccontextmanager
    async def fake_insecure_channel(_addr):
        yield object()

    monkeypatch.setattr(profile_client.grpc.aio, "insecure_channel", fake_insecure_channel)
    monkeypatch.setattr(
        profile_client.profile_pb2_grpc, "ProfileServiceStub", lambda _channel: profile_stub
    )
    monkeypatch.setattr(
        profile_client.profile_pb2_grpc, "CapabilityServiceStub", lambda _channel: capability_stub
    )
    monkeypatch.setattr(
        profile_client.profile_pb2_grpc, "ActivityServiceStub", lambda _channel: activity_stub
    )
    monkeypatch.setattr(
        profile_client.learning_pb2_grpc, "LearningServiceStub", lambda _channel: learning_stub
    )


@pytest.mark.anyio
async def test_no_profile_returns_empty_without_dialing(monkeypatch):
    async def fail_channel(_addr):
        raise AssertionError("no debería intentar conectar sin perfil")

    monkeypatch.setattr(profile_client.grpc.aio, "insecure_channel", fail_channel)

    assert await profile_client.list_allowed_capabilities(None) == []
    assert await profile_client.list_allowed_capabilities("") == []


@pytest.mark.anyio
async def test_intersects_profile_capabilities_with_catalog(monkeypatch):
    profiles = [
        profile_pb2.Profile(name="dev", capabilities=["common.grep-search", "common.unrelated"]),
    ]
    _patch_channel(
        monkeypatch,
        profile_stub=_FakeProfileStub(profiles),
        capability_stub=_FakeCapabilityStub(_caps("common.grep-search", "git.diff")),
    )

    result = await profile_client.list_allowed_capabilities("dev")
    assert [c.id for c in result] == ["common.grep-search"]


@pytest.mark.anyio
async def test_intersection_returns_full_capability_metadata(monkeypatch):
    profiles = [profile_pb2.Profile(name="dev", capabilities=["common.grep-search"])]
    rich_cap = profile_pb2.Capability(
        id="common.grep-search",
        description="Busca patrones.",
        entrypoint="capabilities/common/scripts/core/search/grep_search.py",
        language="python",
        parameters=[profile_pb2.Parameter(name="pattern", required=True)],
    )
    _patch_channel(
        monkeypatch,
        profile_stub=_FakeProfileStub(profiles),
        capability_stub=_FakeCapabilityStub([rich_cap]),
    )

    result = await profile_client.list_allowed_capabilities("dev")
    assert len(result) == 1
    assert result[0].description == "Busca patrones."
    assert result[0].entrypoint == "capabilities/common/scripts/core/search/grep_search.py"
    assert result[0].parameters[0].name == "pattern"


@pytest.mark.anyio
async def test_unknown_profile_name_returns_empty(monkeypatch):
    _patch_channel(
        monkeypatch,
        profile_stub=_FakeProfileStub([profile_pb2.Profile(name="other", capabilities=[])]),
        capability_stub=_FakeCapabilityStub(_caps("common.grep-search")),
    )

    assert await profile_client.list_allowed_capabilities("dev") == []


@pytest.mark.anyio
async def test_list_allowed_capabilities_fails_closed_on_rpc_error(monkeypatch):
    @asynccontextmanager
    async def fake_insecure_channel(_addr):
        raise ConnectionRefusedError("profile server down")
        yield  # pragma: no cover — hace de este un generador

    monkeypatch.setattr(profile_client.grpc.aio, "insecure_channel", fake_insecure_channel)

    assert await profile_client.list_allowed_capabilities("dev") == []


@pytest.mark.anyio
async def test_get_capability_script_returns_source_and_language(monkeypatch):
    _patch_channel(
        monkeypatch,
        capability_stub=_FakeCapabilityStub([], script=("cHJpbnQoMSk=", "python")),
    )

    result = await profile_client.get_capability_script("common.grep-search")
    assert result == ("cHJpbnQoMSk=", "python", {})


@pytest.mark.anyio
async def test_get_capability_script_returns_extra_files(monkeypatch):
    _patch_channel(
        monkeypatch,
        capability_stub=_FakeCapabilityStub(
            [], script=("cHJpbnQoMSk=", "python", {"_report_paths.py": "aGVscGVy"})
        ),
    )

    result = await profile_client.get_capability_script("common.commit-report")
    assert result == ("cHJpbnQoMSk=", "python", {"_report_paths.py": "aGVscGVy"})


@pytest.mark.anyio
async def test_get_capability_script_is_best_effort_on_failure(monkeypatch):
    @asynccontextmanager
    async def fake_insecure_channel(_addr):
        raise ConnectionRefusedError("profile server down")
        yield  # pragma: no cover

    monkeypatch.setattr(profile_client.grpc.aio, "insecure_channel", fake_insecure_channel)

    assert await profile_client.get_capability_script("common.grep-search") is None


@pytest.mark.anyio
async def test_record_activity_reaches_stub(monkeypatch):
    activity_stub = _FakeActivityStub()
    _patch_channel(monkeypatch, activity_stub=activity_stub)

    await profile_client.record_activity(
        capability_id="common.grep-search", profile="dev", status="success", summary="ok"
    )

    assert len(activity_stub.recorded) == 1
    assert activity_stub.recorded[0].capability_id == "common.grep-search"


@pytest.mark.anyio
async def test_record_activity_is_best_effort_on_failure(monkeypatch):
    @asynccontextmanager
    async def fake_insecure_channel(_addr):
        raise ConnectionRefusedError("profile server down")
        yield  # pragma: no cover

    monkeypatch.setattr(profile_client.grpc.aio, "insecure_channel", fake_insecure_channel)

    # No debe levantar excepción — best-effort.
    await profile_client.record_activity(
        capability_id="common.grep-search", profile="dev", status="failure"
    )


@pytest.mark.anyio
async def test_record_learning_texts_reaches_learning_service(monkeypatch):
    learning_stub = _FakeLearningStub()
    _patch_channel(monkeypatch, learning_stub=learning_stub)

    await profile_client.record_learning_texts(
        learning_event_id="event-1",
        thoughts=[
            {
                "seq": 2,
                "content": "Se ejecutó una validación.",
                "tool_name": "Bash",
                "outcome": "success",
                "tokens": 1975,
                "output_text": "Bash (success), 1975 tokens estimados.",
            }
        ],
    )

    assert len(learning_stub.recorded) == 1
    text = learning_stub.recorded[0].text
    assert text.learning_event_id == "event-1"
    assert text.text_kind == "thought"
    assert text.tool_name == "Bash"
    assert text.tokens == 1975
    assert text.output_text == "Bash (success), 1975 tokens estimados."
