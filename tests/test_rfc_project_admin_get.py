"""RFC-0030 paquete 6: la acción get de common.rfc-project-admin lee un RFC completo.

Ejecuta el código REAL registrado en la DB del profile-server (no una copia) contra un
rules-api de juguete que registra cada petición. Se salta si el profile-server no
responde o la capability aún no está registrada.
"""

import asyncio
import base64
import binascii
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from higpertext_mcp import profile_client

CAPABILITY_ID = "common.rfc-project-admin"
TOKEN = "token-de-prueba"


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
    path = tmp_path_factory.mktemp("rfc_project_admin") / "rfc_project_admin.py"
    path.write_text(_decode(found[0]), encoding="utf-8")
    return path


@pytest.fixture
def api():
    requests: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def _reply(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode() if length else ""
            requests.append(
                {
                    "method": self.command,
                    "path": self.path,
                    "body": json.loads(body) if body else None,
                    "auth": self.headers.get("Authorization"),
                    "agent": self.headers.get("X-Higpertext-Agent"),
                }
            )
            if self.command == "GET" and self.path == "/api/rfcs":
                payload, status = [{"id": "RFC-0030"}], 200
            elif self.command == "GET":
                payload, status = {"id": self.path.rsplit("/", 1)[-1], "state": "aprobado"}, 200
            else:
                payload, status = {"type": "comentario"}, 201
            raw = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        do_GET = do_POST = do_PATCH = do_DELETE = do_PUT = _reply

        def log_message(self, *args):  # silencio en la salida de pytest
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", requests
    finally:
        server.shutdown()
        server.server_close()


def _run(script_path, base, *args, token=TOKEN):
    env = {"PATH": "/usr/bin:/bin", "HTX_RFC_API": base, "HTX_RFC_MCP_TOKEN": token}
    return subprocess.run(
        [sys.executable, str(script_path), *args], env=env, capture_output=True, text=True, timeout=30
    )


def test_get_reads_one_full_rfc_with_get_only(script_path, api):
    base, requests = api
    got = _run(script_path, base, "--action", "get", "--rfc_id", "rfc-0030")

    assert got.returncode == 0 and json.loads(got.stdout)["rfc"]["id"] == "RFC-0030"
    assert [(r["method"], r["path"]) for r in requests] == [("GET", "/api/rfcs/RFC-0030")]
    assert requests[0]["auth"] == f"Bearer {TOKEN}"


def test_get_requires_a_valid_rfc_id_before_any_request(script_path, api):
    base, requests = api
    missing = _run(script_path, base, "--action", "get")
    invalid = _run(script_path, base, "--action", "get", "--rfc_id", "../etc/passwd")

    assert missing.returncode != 0 and invalid.returncode != 0
    assert requests == []


def test_get_fails_without_credentials_and_sends_nothing(script_path, api):
    base, requests = api
    done = _run(script_path, base, "--action", "get", "--rfc_id", "RFC-0030", token="")

    assert done.returncode != 0
    assert requests == []
