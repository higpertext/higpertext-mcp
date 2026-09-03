"""Lanzador HTTP standalone para higpertext-mcp.

No modifica higpertext_mcp/server.py: reusa build_server() (transport-agnostic)
y lo expone via Streamable HTTP en localhost, evitando por completo
flatpak-spawn --host, que se demostró poco fiable para el transporte stdio
cuando el proceso que invoca corre dentro del sandbox de Postman (Electron).
"""

from __future__ import annotations

import contextlib
import os

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from higpertext_mcp import external, server as higpertext_server

HOST = "127.0.0.1"
PORT = int(os.environ.get("HIGPERTEXT_MCP_HTTP_PORT", "8790"))

# DNS-rebinding / CSRF hardening: solo acepta requests cuyo Host coincida
# exactamente con este bind y sin Origin de navegador ajeno. Sin esto, cualquier
# pestaña del navegador podría hacer fetch() a este puerto local.
SECURITY_SETTINGS = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[f"{HOST}:{PORT}"],
    allowed_origins=[],
)


class _StreamableHTTPASGIApp:
    def __init__(self, session_manager: StreamableHTTPSessionManager) -> None:
        self.session_manager = session_manager

    async def __call__(self, scope, receive, send) -> None:
        await self.session_manager.handle_request(scope, receive, send)


def build_app() -> Starlette:
    mcp_server = higpertext_server.build_server(external.ExternalServerPool([]))
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server, stateless=True, security_settings=SECURITY_SETTINGS
    )
    asgi_app = _StreamableHTTPASGIApp(session_manager)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with session_manager.run():
            yield

    return Starlette(routes=[Mount("/mcp", app=asgi_app)], lifespan=lifespan)


app = build_app()

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
