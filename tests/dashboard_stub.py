"""Stub de rules-api para los tests de higpertext-dashboard.

Levanta un servidor HTTP real en 127.0.0.1 que registra cada request y responde lo que
cada test encola, y un proveedor de token de servicio falso. Así los tests ejercitan el
cliente REST completo (cabeceras, reintentos, redirecciones, tamaños, timeouts) sin red
externa ni Keycloak.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qsl, urlparse

import pytest

from higpertext_mcp import auth
from higpertext_mcp.http_auth import ApiTokenContext


@dataclass
class Reply:
    status: int = 200
    body: Any = None
    raw: bytes | None = None
    headers: dict[str, str] = field(default_factory=dict)
    delay: float = 0.0
    content_type: str = "application/json"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args: Any) -> None:  # silencio
        pass

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body: Any = json.loads(raw) if raw else None
        except ValueError:
            body = raw.decode("utf-8", "replace")
        parsed = urlparse(self.path)
        stub: StubRulesApi = self.server.stub  # type: ignore[attr-defined]
        stub.requests.append({
            "method": self.command, "path": parsed.path, "query": dict(parse_qsl(parsed.query)),
            "headers": {key.lower(): value for key, value in self.headers.items()}, "body": body,
        })
        reply = stub.next_reply()
        if reply.delay:
            time.sleep(reply.delay)
        if reply.raw is not None:
            payload = reply.raw
        else:
            payload = b"" if reply.body is None else json.dumps(reply.body).encode()
        self.send_response(reply.status)
        for key, value in reply.headers.items():
            self.send_header(key, value)
        self.send_header("Content-Type", reply.content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _handle


class StubRulesApi:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.default = Reply(200, {})
        self._queue: list[Reply] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.stub = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> "StubRulesApi":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def queue(self, status: int = 200, body: Any = None, **kwargs: Any) -> "StubRulesApi":
        self._queue.append(Reply(status=status, body=body, **kwargs))
        return self

    def next_reply(self) -> Reply:
        return self._queue.pop(0) if self._queue else self.default


class FakeProvider:
    """Cuenta de servicio falsa: ``invalidate()`` hace que el siguiente token sea otro."""

    def __init__(self, *tokens: str) -> None:
        self.tokens = list(tokens) or ["svc-token-1"]
        self.invalidations = 0
        self.issued = 0

    async def token(self) -> str:
        self.issued += 1
        return self.tokens[min(self.invalidations, len(self.tokens) - 1)]

    def invalidate(self) -> None:
        self.invalidations += 1


def api_token(user_id: str = "user-1", scopes: tuple[str, ...] = ("administración",),
              repository_ids: tuple[str, ...] = ()) -> ApiTokenContext:
    return ApiTokenContext(
        token_id="token-1", user_id=user_id, scopes=frozenset(scopes), profile="",
        organization_ids=frozenset(), repository_ids=frozenset(repository_ids),
    )


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    fake = FakeProvider("svc-token-1", "svc-token-2")
    monkeypatch.setattr(auth, "default_provider", lambda: fake)
    return fake


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, provider: FakeProvider):
    stub = StubRulesApi().start()
    monkeypatch.delenv("HTX_RFC_API", raising=False)
    monkeypatch.setenv("HTX_RULES_API_URL", stub.base)
    yield stub
    stub.stop()
