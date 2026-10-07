"""RFC-0030 paquete 3: common.rfc-transition actúa con la identidad del propio agente.

Ejecuta el código REAL registrado en la DB del profile-server contra un servidor de juguete
que hace de Keycloak (/token) y de rules-api (/api/...) y registra cada petición. Se salta si
el profile-server no responde o la capability aún no está registrada.
"""

import asyncio
import base64
import binascii
import json
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from higpertext_mcp import profile_client

CAPABILITY_ID = "common.rfc-transition"
AGENT_SECRET = "secreto-del-agente-NO-FILTRAR"
AGENT_TOKEN = "access-token-del-agente"
SHARED_MCP_TOKEN = "token-compartido-del-mcp"
SYNC_TOKEN = "token-del-sincronizador"


def _decode(source: str) -> str:
    try:
        return base64.b64decode(source, validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return source


@pytest.fixture(scope="module")
def script_path(tmp_path_factory):
    found = asyncio.run(profile_client.get_capability_script(CAPABILITY_ID))
    if not found or not found[0]:
        pytest.skip(f"{CAPABILITY_ID} no disponible en el profile-server")
    path = tmp_path_factory.mktemp("rfc_transition") / "rfc_transition.py"
    path.write_text(_decode(found[0]), encoding="utf-8")
    return path


class _State:
    def __init__(self):
        self.requests: list[dict] = []
        self.token_status = 200
        self.rules_status = 200
        self.rules_body = {"id": "RFC-0030", "state": "desarrollo"}

    def api(self):
        return [r for r in self.requests if r["path"].startswith("/api/")]

    def tokens(self):
        return [r for r in self.requests if r["path"] == "/token"]


@pytest.fixture
def stub():
    state = _State()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode() if length else ""
            if self.path == "/token":
                state.requests.append({"path": "/token", "form": dict(urllib.parse.parse_qsl(raw))})
                status = state.token_status
                payload = {"access_token": AGENT_TOKEN, "expires_in": 60} if status == 200 else {"error": "invalid_client"}
            else:
                state.requests.append(
                    {"path": self.path, "method": "POST", "body": json.loads(raw) if raw else None,
                     "auth": self.headers.get("Authorization")}
                )
                status, payload = state.rules_status, state.rules_body
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state.base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()


def _run(script_path, stub, *args, secret=AGENT_SECRET):
    env = {
        "PATH": "/usr/bin:/bin",
        "HTX_RFC_API": stub.base,
        "HIGPERTEXT_OIDC_TOKEN_URL": stub.base + "/token",
        "HIGPERTEXT_AGENT_CLIENT_ID": "htx-agent",
        # Señuelos: el script jamás debe usarlos.
        "HTX_RFC_MCP_TOKEN": SHARED_MCP_TOKEN,
        "HTX_RFC_WRITE_TOKEN": SYNC_TOKEN,
    }
    if secret:
        env["HIGPERTEXT_AGENT_CLIENT_SECRET"] = secret
    return subprocess.run(
        [sys.executable, str(script_path), *args], env=env, capture_output=True, text=True, timeout=30
    )


def _transition(script_path, stub, **extra):
    args = ["--action", "transition", "--rfc_id", "rfc-0030", "--to", "revision"]
    for key, value in extra.items():
        args += [f"--{key}", str(value)]
    return _run(script_path, stub, *args)


def test_sends_agent_bearer(script_path, stub):
    done = _transition(script_path, stub, version=7, note="listo para revisión")

    assert done.returncode == 0 and json.loads(done.stdout)["ok"] is True
    assert stub.tokens()[0]["form"] == {
        "grant_type": "client_credentials", "client_id": "htx-agent", "client_secret": AGENT_SECRET,
    }
    assert stub.api() == [
        {
            "path": "/api/rfcs/RFC-0030/transition",
            "method": "POST",
            "body": {"to": "revision", "note": "listo para revisión", "version": 7},
            "auth": f"Bearer {AGENT_TOKEN}",
        }
    ]


def test_not_using_sync_or_mcp_token(script_path, stub):
    _transition(script_path, stub)
    _run(script_path, stub, "--action", "vote", "--rfc_id", "RFC-0030", "--text", "ok")

    assert stub.api()
    for request in stub.api():
        assert request["auth"] == f"Bearer {AGENT_TOKEN}"
        assert SHARED_MCP_TOKEN not in request["auth"] and SYNC_TOKEN not in request["auth"]


@pytest.mark.parametrize("status", [401, 403, 409])
def test_propagates_401_403_409(script_path, stub, status):
    stub.rules_status = status
    stub.rules_body = {"error": f"detalle-del-servidor-{status}"}
    done = _transition(script_path, stub)

    assert done.returncode != 0
    output = done.stdout + done.stderr
    assert f"HTTP {status}" in output and f"detalle-del-servidor-{status}" in output


def test_mutation_never_retried(script_path, stub):
    stub.rules_status = 401
    done = _transition(script_path, stub)

    assert done.returncode != 0
    assert len(stub.api()) == 1


def test_token_is_obtained_on_every_call_without_cache(script_path, stub):
    _transition(script_path, stub)
    _transition(script_path, stub)

    assert len(stub.tokens()) == 2 and len(stub.api()) == 2


def test_secret_not_logged(script_path, stub):
    ok = _transition(script_path, stub)
    stub.rules_status = 403
    denied = _transition(script_path, stub)
    stub.token_status = 401
    bad_credentials = _transition(script_path, stub)

    for done in (ok, denied, bad_credentials):
        assert AGENT_SECRET not in done.stdout + done.stderr
    assert bad_credentials.returncode != 0 and "Keycloak rechazó las credenciales" in bad_credentials.stderr


def test_vote_response_marked_informative(script_path, stub):
    stub.rules_status = 201
    stub.rules_body = {"type": "comentario"}
    done = _run(script_path, stub, "--action", "vote", "--rfc_id", "RFC-0030",
                "--text", "Plan revisado", "--verdict", "aprobar")

    result = json.loads(done.stdout)
    assert done.returncode == 0 and result["informative"] is True
    assert "no es un voto aprobatorio" in result["notice"]
    assert stub.api() == [
        {
            "path": "/api/rfcs/RFC-0030/comments",
            "method": "POST",
            "body": {"text": "Plan revisado", "verdict": "aprobar"},
            "auth": f"Bearer {AGENT_TOKEN}",
        }
    ]


def test_missing_secret_fails_without_any_request(script_path, stub):
    done = _run(script_path, stub, "--action", "transition", "--rfc_id", "RFC-0030", "--to", "revision", secret="")

    assert done.returncode != 0 and "HIGPERTEXT_AGENT_CLIENT_SECRET" in done.stderr
    assert stub.requests == []


@pytest.mark.parametrize(
    "args",
    [
        ["--action", "transition", "--rfc_id", "RFC-0030", "--to", "inventado"],
        ["--action", "transition", "--rfc_id", "../etc", "--to", "revision"],
        ["--action", "transition", "--rfc_id", "RFC-0030", "--to", "revision", "--version", "abc"],
        ["--action", "transition", "--rfc_id", "RFC-0030", "--to", "revision", "--note", "x" * 1001],
        ["--action", "vote", "--rfc_id", "RFC-0030", "--text", "  "],
        ["--action", "vote", "--rfc_id", "RFC-0030", "--text", "x" * 2001],
        ["--action", "approve", "--rfc_id", "RFC-0030"],
    ],
)
def test_invalid_input_is_rejected_before_any_request(script_path, stub, args):
    done = _run(script_path, stub, *args)

    assert done.returncode != 0
    assert stub.requests == []


def test_source_never_references_the_shared_tokens(script_path):
    source = script_path.read_text(encoding="utf-8")

    for forbidden in ("HTX_RFC_MCP_TOKEN", "HTX_RFC_WRITE_TOKEN"):
        assert forbidden not in source
