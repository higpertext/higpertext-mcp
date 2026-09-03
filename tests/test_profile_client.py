"""Cobertura de profile_client.py con un canal/stub gRPC fake — sin depender
de un profile server real corriendo, mismo criterio que memory.py/test_memory.py
usa para Redis."""

from contextlib import asynccontextmanager

import grpc
import pytest

from higpertext_mcp import profile_client
from higpertext_mcp.gen.profile.v1 import profile_pb2


class _FakeProfileStub:
    def __init__(self, profiles: list[profile_pb2.Profile]) -> None:
        self._profiles = profiles

    async def ListProfiles(self, _request, timeout=None):
        return profile_pb2.ListProfilesResponse(profiles=self._profiles)


class _FakeCapabilityStub:
    def __init__(self, capability_ids: list[str]) -> None:
        self._capability_ids = capability_ids

    async def ListCapabilities(self, _request, timeout=None):
        return profile_pb2.ListCapabilitiesResponse(
            capabilities=[profile_pb2.Capability(id=cid) for cid in self._capability_ids]
        )


class _FakeActivityStub:
    def __init__(self) -> None:
        self.recorded: list[profile_pb2.RecordActivityRequest] = []

    async def RecordActivity(self, request, timeout=None):
        self.recorded.append(request)
        return profile_pb2.RecordActivityResponse(activity=profile_pb2.Activity(id="fake-id"))


def _patch_channel(monkeypatch, *, profile_stub=None, capability_stub=None, activity_stub=None):
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


@pytest.mark.anyio
async def test_no_profile_returns_empty_without_dialing(monkeypatch):
    async def fail_channel(_addr):
        raise AssertionError("no debería intentar conectar sin perfil")

    monkeypatch.setattr(profile_client.grpc.aio, "insecure_channel", fail_channel)

    assert await profile_client.list_allowed_capability_ids(None) == []
    assert await profile_client.list_allowed_capability_ids("") == []


@pytest.mark.anyio
async def test_intersects_profile_capabilities_with_catalog(monkeypatch):
    profiles = [
        profile_pb2.Profile(name="dev", capabilities=["common.grep-search", "common.unrelated"]),
    ]
    _patch_channel(
        monkeypatch,
        profile_stub=_FakeProfileStub(profiles),
        capability_stub=_FakeCapabilityStub(["common.grep-search", "git.diff"]),
    )

    result = await profile_client.list_allowed_capability_ids("dev")
    assert result == ["common.grep-search"]


@pytest.mark.anyio
async def test_unknown_profile_name_returns_empty(monkeypatch):
    _patch_channel(
        monkeypatch,
        profile_stub=_FakeProfileStub([profile_pb2.Profile(name="other", capabilities=[])]),
        capability_stub=_FakeCapabilityStub(["common.grep-search"]),
    )

    assert await profile_client.list_allowed_capability_ids("dev") == []


@pytest.mark.anyio
async def test_list_allowed_capability_ids_fails_closed_on_rpc_error(monkeypatch):
    @asynccontextmanager
    async def fake_insecure_channel(_addr):
        raise ConnectionRefusedError("profile server down")
        yield  # pragma: no cover — hace de este un generador

    monkeypatch.setattr(profile_client.grpc.aio, "insecure_channel", fake_insecure_channel)

    assert await profile_client.list_allowed_capability_ids("dev") == []


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
