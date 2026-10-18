"""Cliente REST de dashboards: delegación de identidad, reintentos, errores y límites."""

import json

import pytest

from dashboard_stub import FakeProvider, StubRulesApi, api, provider  # noqa: F401 — fixtures
from higpertext_mcp.dashboard_client import (
    DashboardApiError,
    DashboardClient,
    DashboardClientError,
    DashboardUnavailable,
)


@pytest.mark.anyio
async def test_client_sends_service_bearer_and_on_behalf_header(api, provider):
    api.queue(200, {"id": "abc"})
    api.queue(201, {"action": "created"})
    client = DashboardClient()
    assert await client.request("GET", "abc", on_behalf_of="user-1") == {"id": "abc"}
    assert await client.request("POST", "import", on_behalf_of="user-1", body={"title": "T"}) == {"action": "created"}
    first, second = api.requests
    assert first["method"] == "GET" and first["path"] == "/api/dashboards/abc"
    assert first["headers"]["authorization"] == "Bearer svc-token-1"
    assert first["headers"]["x-htx-on-behalf-of"] == "user-1"
    assert second["method"] == "POST" and second["path"] == "/api/dashboards/import"
    assert second["body"] == {"title": "T"} and second["headers"]["content-type"] == "application/json"
    # La base sale de HTX_RULES_API_URL (el stub): una llamada llegó a este servidor.
    assert len(api.requests) == 2
    # Nada del PAT del cliente viaja: solo el bearer de servicio y el user_id.
    assert set(first["headers"]) >= {"authorization", "x-htx-on-behalf-of"}
    assert "pat" not in json.dumps(first["headers"]).lower()


@pytest.mark.anyio
async def test_client_retries_once_after_401_and_invalidates_token(api, provider):
    api.queue(401, {"error": "token vencido"}).queue(200, {"ok": True})
    assert await DashboardClient().request("GET", on_behalf_of="user-1") == {"ok": True}
    assert len(api.requests) == 2
    assert provider.invalidations == 1
    assert api.requests[0]["headers"]["authorization"] == "Bearer svc-token-1"
    assert api.requests[1]["headers"]["authorization"] == "Bearer svc-token-2"

    api.requests.clear()
    api.default = api.default.__class__(401, {"error": "sigue sin autorización"})
    with pytest.raises(DashboardApiError) as caught:
        await DashboardClient().request("GET", on_behalf_of="user-1")
    assert caught.value.status == 401 and caught.value.code == "unauthorized"
    assert len(api.requests) == 2  # exactamente un reintento


@pytest.mark.anyio
async def test_client_maps_http_errors_to_dashboard_api_error(api, provider):
    cases = [
        (400, b"settings inv\xc3\xa1lido", "bad_request", "settings inválido"),
        (403, json.dumps({"error": {"code": "forbidden", "message": "no tenés acceso"}}).encode(), "forbidden", "no tenés acceso"),
        (404, b"404 page not found", "not_found", "404 page not found"),
        (409, json.dumps({"error": "conflicto de versión", "currentVersion": 3}).encode(), "conflict", "conflicto de versión"),
        (500, b"boom", "server_error", "boom"),
    ]
    for status, raw, code, message in cases:
        api.requests.clear()
        api.queue(status, raw=raw)
        with pytest.raises(DashboardApiError) as caught:
            await DashboardClient().request("GET", "abc", on_behalf_of="user-1")
        error = caught.value
        assert (error.status, error.code, error.message) == (status, code, message), (status, error.code, error.message)
        assert len(api.requests) == 1, f"{status} no debe reintentarse"
    assert error.status == 500
    # El 409 conserva currentVersion para que la tool lo exponga.
    api.queue(409, {"error": "conflicto", "currentVersion": 7})
    with pytest.raises(DashboardApiError) as conflict:
        await DashboardClient().request("POST", "abc", "versions", 2, "restore", on_behalf_of="user-1")
    assert conflict.value.payload["currentVersion"] == 7
    assert api.requests[-1]["path"] == "/api/dashboards/abc/versions/2/restore"


@pytest.mark.anyio
async def test_client_rejects_missing_on_behalf_of_and_bad_ids_before_any_request(api, provider):
    client = DashboardClient()
    for behalf in ("", "   ", None, "a/b", "x" * 200, "u\nv", "../u"):
        with pytest.raises(DashboardClientError):
            await client.request("GET", "abc", on_behalf_of=behalf)  # type: ignore[arg-type]
    for segment in ("..", "../x", "a/b", "", "x?y", "a b", ".hidden", "x" * 65, True):
        with pytest.raises(DashboardClientError):
            await client.request("GET", segment, on_behalf_of="user-1")  # type: ignore[arg-type]
    with pytest.raises(DashboardClientError):
        await client.request("GET", "abc", "versions", "2/../3", on_behalf_of="user-1")
    assert api.requests == []
    assert provider.issued == 0


@pytest.mark.anyio
async def test_client_does_not_follow_redirects(api, provider):
    api.queue(302, raw=b"", headers={"Location": api.base + "/api/projects"})
    with pytest.raises(DashboardApiError) as caught:
        await DashboardClient().request("GET", "abc", on_behalf_of="user-1")
    assert caught.value.status == 302 and caught.value.code == "unexpected_redirect"
    assert len(api.requests) == 1, "el bearer de servicio no debe seguir una redirección"


@pytest.mark.anyio
async def test_client_connection_refused_and_timeout_are_unavailable(api, provider):
    with pytest.raises(DashboardUnavailable) as refused:
        await DashboardClient(base_url="http://127.0.0.1:1").request("GET", on_behalf_of="user-1")
    assert refused.value.code == "unavailable"
    api.queue(200, {}, delay=1.5)
    with pytest.raises(DashboardUnavailable) as slow:
        await DashboardClient(timeout=0.2).request("GET", on_behalf_of="user-1")
    assert slow.value.code == "timeout"
    assert "127.0.0.1" not in str(refused.value) and "svc-token" not in str(slow.value)


@pytest.mark.anyio
async def test_client_errors_never_include_secrets(api, provider):
    hostile = [
        json.dumps({"error": "falló con Bearer svc-token-1 adentro", "token": "svc-token-1", "nested": {"x": "svc-token-1"}}).encode(),
        b"plain svc-token-1 and Bearer abc.def-123",
        json.dumps({"error": {"code": "svc-token-1", "message": "Bearer svc-token-1"}}).encode(),
    ]
    for raw in hostile:
        api.queue(500, raw=raw)
        with pytest.raises(DashboardApiError) as caught:
            await DashboardClient().request("GET", on_behalf_of="user-1")
        error = caught.value
        for rendered in (error.message, str(error), repr(error), json.dumps(error.payload), error.code):
            assert "svc-token-1" not in rendered, rendered
            assert "abc.def-123" not in rendered, rendered


@pytest.mark.anyio
async def test_client_enforces_response_size_cap(api, provider):
    cap = 100
    padding = cap - len('{"d":""}')
    exact = ('{"d":"' + "x" * padding + '"}').encode()
    assert len(exact) == cap
    api.queue(200, raw=exact)
    assert (await DashboardClient(max_response_bytes=cap).request("GET", on_behalf_of="user-1"))["d"] == "x" * padding
    api.queue(200, raw=exact + b" ")
    with pytest.raises(DashboardApiError) as too_big:
        await DashboardClient(max_response_bytes=cap).request("GET", on_behalf_of="user-1")
    assert too_big.value.code == "response_too_large"
    api.queue(500, raw=b"e" * 300)
    with pytest.raises(DashboardApiError) as too_big_error:
        await DashboardClient(max_response_bytes=cap).request("GET", on_behalf_of="user-1")
    assert too_big_error.value.code == "response_too_large"
