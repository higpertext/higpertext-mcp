"""Lanzador HTTP standalone para higpertext-mcp.

No modifica higpertext_mcp/server.py: reusa build_server() (transport-agnostic)
y lo expone via Streamable HTTP en localhost, evitando por completo
flatpak-spawn --host, que se demostró poco fiable para el transporte stdio
cuando el proceso que invoca corre dentro del sandbox de Postman (Electron).
"""

from __future__ import annotations

import contextlib
import os
import asyncio

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from higpertext_mcp import discovery, external, platform_logs, server as higpertext_server

# Dentro de Docker debe escuchar en todas las interfaces para que el puerto
# publicado sea accesible desde el host. La protección DNS/CSRF de abajo sigue
# limitando los encabezados Host aceptados a los nombres locales esperados.
HOST = os.environ.get("HIGPERTEXT_MCP_HTTP_HOST", "0.0.0.0")
PORT = int(os.environ.get("HIGPERTEXT_MCP_HTTP_PORT", "8790"))

# DNS-rebinding / CSRF hardening: solo acepta requests cuyo Host coincida
# exactamente con este bind y sin Origin de navegador ajeno. Sin esto, cualquier
# pestaña del navegador podría hacer fetch() a este puerto local.
SECURITY_SETTINGS = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[f"127.0.0.1:{PORT}", f"localhost:{PORT}", f"{HOST}:{PORT}"],
    allowed_origins=[],
)


class _StreamableHTTPASGIApp:
    def __init__(self, session_manager: StreamableHTTPSessionManager) -> None:
        self.session_manager = session_manager

    async def __call__(self, scope, receive, send) -> None:
        await self.session_manager.handle_request(scope, receive, send)


def build_app() -> Starlette:
    # ExternalServerPool real, no [] hardcodeado: sin esto, ningún server
    # declarado en `.higpertext/config/mcp_external.json` (telemetry,
    # controller, ...) queda federado bajo `external.<name>.<tool>` cuando
    # el gateway corre por HTTP (Docker) — el modo stdio (server.py:_amain)
    # sí lo cargaba, este entrypoint HTTP no.
    root = discovery.resolve_project_root()
    configs = external.load_external_servers(root)
    pool = external.ExternalServerPool(configs)
    mcp_server = higpertext_server.build_server(pool)
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server, stateless=True, security_settings=SECURITY_SETTINGS
    )
    asgi_app = _StreamableHTTPASGIApp(session_manager)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with pool, session_manager.run():
            stop = asyncio.Event()
            async def collect() -> None:
                while not stop.is_set():
                    await platform_logs.ingest(discovery.resolve_project_root())
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=10)
                    except TimeoutError:
                        pass
            task = asyncio.create_task(collect())
            try:
                yield
            finally:
                stop.set()
                await task

    async def health(_request) -> JSONResponse:
        return JSONResponse({"ok": True, "service": "higpertext-mcp"})

    return Starlette(
        routes=[Route("/health", health), Mount("/mcp", app=asgi_app)], lifespan=lifespan
    )


app = build_app()

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
