import asyncio

import pytest

from higpertext_mcp import auth, config

pytestmark = pytest.mark.anyio


class FakeKeycloak:
    def __init__(self, expires_in=300, fail: Exception | None = None):
        self.calls: list[tuple[str, dict]] = []
        self.expires_in = expires_in
        self.fail = fail

    def __call__(self, url, form):
        self.calls.append((url, dict(form)))
        if self.fail:
            raise self.fail
        return {"access_token": f"tok-{len(self.calls)}", "expires_in": self.expires_in}


class Clock:
    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now


def make(fake, clock=None, secret="s3cr3t"):
    return auth.ServiceTokenProvider(
        token_url="http://kc/token", client_id="htx-agent", client_secret=secret, fetch=fake, clock=clock or Clock(),
    )


async def test_requests_client_credentials_and_caches():
    fake = FakeKeycloak()
    provider = make(fake)
    assert await provider.token() == "tok-1"
    assert await provider.token() == "tok-1"
    assert len(fake.calls) == 1
    url, form = fake.calls[0]
    assert url == "http://kc/token"
    assert form == {"grant_type": "client_credentials", "client_id": "htx-agent", "client_secret": "s3cr3t"}


async def test_refreshes_before_expiry():
    fake, clock = FakeKeycloak(expires_in=100), Clock()
    provider = make(fake, clock)
    assert await provider.token() == "tok-1"
    clock.now += 60  # aún dentro de la ventana válida (100 - 30 de margen)
    assert await provider.token() == "tok-1"
    clock.now += 20  # 80 s > 100 - 30: debe renovar
    assert await provider.token() == "tok-2"


async def test_concurrent_callers_share_one_request():
    fake = FakeKeycloak()
    provider = make(fake)
    tokens = await asyncio.gather(*(provider.token() for _ in range(10)))
    assert set(tokens) == {"tok-1"}
    assert len(fake.calls) == 1


async def test_invalidate_forces_new_token():
    fake = FakeKeycloak()
    provider = make(fake)
    await provider.token()
    provider.invalidate()
    assert await provider.token() == "tok-2"


async def test_headers_are_bearer():
    assert await make(FakeKeycloak()).headers() == {"Authorization": "Bearer tok-1"}


async def test_missing_secret_is_explained_without_calling_keycloak(monkeypatch):
    monkeypatch.delenv("HIGPERTEXT_AGENT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("HIGPERTEXT_AGENT_CLIENT_SECRET_FILE", raising=False)
    fake = FakeKeycloak()
    provider = auth.ServiceTokenProvider(token_url="http://kc/token", fetch=fake)
    with pytest.raises(auth.AuthError, match="HIGPERTEXT_AGENT_CLIENT_SECRET"):
        await provider.token()
    assert fake.calls == []


async def test_errors_never_leak_the_secret():
    provider = make(FakeKeycloak(fail=auth.AuthError(auth._describe_http_failure(401, "invalid_client"))))
    with pytest.raises(auth.AuthError) as info:
        await provider.token()
    assert "invalid_client" in str(info.value)
    assert "s3cr3t" not in str(info.value)


def test_http_failure_messages():
    assert "service account" in auth._describe_http_failure(400, "unauthorized_client")
    assert "invalid_client" in auth._describe_http_failure(401, "")
    assert "HTTP 500" in auth._describe_http_failure(500, "")


async def test_bad_response_without_token():
    class NoToken:
        def __call__(self, url, form):
            return {"expires_in": 60}

    with pytest.raises(auth.AuthError, match="access_token"):
        await make(NoToken()).token()


def test_secret_from_file(tmp_path, monkeypatch):
    secret_file = tmp_path / "agent.secret"
    secret_file.write_text("from-file\n")
    monkeypatch.delenv("HIGPERTEXT_AGENT_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("HIGPERTEXT_AGENT_CLIENT_SECRET_FILE", str(secret_file))
    assert config.agent_client_secret() == "from-file"
    monkeypatch.setenv("HIGPERTEXT_AGENT_CLIENT_SECRET", "direct")
    assert config.agent_client_secret() == "direct"


def test_keycloak_unreachable_message(monkeypatch):
    import urllib.error

    def boom(*args, **kwargs):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(auth.urllib.request, "urlopen", boom)
    with pytest.raises(auth.AuthError, match="Keycloak no responde"):
        auth._http_fetch("http://kc/token", {"a": "b"})


def test_host_header_is_forced_only_when_configured(monkeypatch):
    seen = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"access_token": "t", "expires_in": 60}'

    def fake_urlopen(request, timeout):
        seen.append(dict(request.header_items()))
        return Resp()

    monkeypatch.setattr(auth.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.delenv("HIGPERTEXT_OIDC_HOST_HEADER", raising=False)
    auth._http_fetch("http://keycloak:8080/token", {})
    assert "Host" not in seen[0]
    monkeypatch.setenv("HIGPERTEXT_OIDC_HOST_HEADER", "localhost:8081")
    auth._http_fetch("http://keycloak:8080/token", {})
    assert seen[1]["Host"] == "localhost:8081"
