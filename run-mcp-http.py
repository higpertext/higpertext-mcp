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
from urllib.parse import urlsplit

import uvicorn
from pydantic import AnyHttpUrl
from redis.asyncio import Redis
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp.server.auth.handlers.metadata import MetadataHandler
from mcp.server.auth.routes import (
    build_metadata,
    build_resource_metadata_url,
    create_auth_routes,
    create_protected_resource_routes,
)
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from higpertext_mcp import discovery, external, platform_logs, server as higpertext_server
from higpertext_mcp.http_auth import ApiTokenAuth
from higpertext_mcp.oauth_provider import PATOAuthProvider

# Dentro de Docker debe escuchar en todas las interfaces para que el puerto
# publicado sea accesible desde el host. La protección DNS/CSRF de abajo sigue
# limitando los encabezados Host aceptados a los nombres locales esperados.
HOST = os.environ.get("HIGPERTEXT_MCP_HTTP_HOST", "0.0.0.0")
PORT = int(os.environ.get("HIGPERTEXT_MCP_HTTP_PORT", "8790"))
PUBLIC_URL = os.environ.get("HIGPERTEXT_MCP_PUBLIC_URL", f"http://127.0.0.1:{PORT}").rstrip("/")
PUBLIC_HOST = urlsplit(PUBLIC_URL).netloc
PUBLIC_HOSTNAME = urlsplit(PUBLIC_URL).hostname or "127.0.0.1"
ISSUER_URL = AnyHttpUrl(PUBLIC_URL)
RESOURCE_URL = AnyHttpUrl(f"{PUBLIC_URL}/mcp")
RESOURCE_METADATA_URL = str(build_resource_metadata_url(RESOURCE_URL))
OAUTH_REDIS = Redis.from_url(os.environ.get("HIGPERTEXT_REDIS_URL", "redis://127.0.0.1:6379/0"))
API_TOKEN_AUTH = ApiTokenAuth(resource_metadata_url=RESOURCE_METADATA_URL)
OAUTH_PROVIDER = PATOAuthProvider(OAUTH_REDIS, API_TOKEN_AUTH, PUBLIC_URL)

# DNS-rebinding / CSRF hardening: solo acepta requests cuyo Host coincida
# exactamente con este bind y sin Origin de navegador ajeno. Sin esto, cualquier
# pestaña del navegador podría hacer fetch() a este puerto local.
SECURITY_SETTINGS = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[f"127.0.0.1:{PORT}", f"localhost:{PORT}", f"{HOST}:{PORT}", PUBLIC_HOST],
    allowed_origins=[],
)


class _StreamableHTTPASGIApp:
    def __init__(self, session_manager: StreamableHTTPSessionManager) -> None:
        self.session_manager = session_manager

    async def __call__(self, scope, receive, send) -> None:
        # El gateway es compartido: cada cliente declara su proyecto en un
        # header. Sin header se usa HIGPERTEXT_PROJECT_ROOT (compatibilidad).
        header = discovery.PROJECT_ROOT_HEADER.lower().encode()
        selected = next((v for k, v in scope.get("headers", []) if k == header), None)
        if selected is None:
            await self.session_manager.handle_request(scope, receive, send)
            return
        try:
            token = discovery.select_request_project(selected.decode())
        except ValueError as exc:
            await JSONResponse({"error": str(exc)}, status_code=400)(scope, receive, send)
            return
        try:
            await self.session_manager.handle_request(scope, receive, send)
        finally:
            discovery.reset_request_project(token)


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
    # Valida el bearer OAuth en cada request y propaga los alcances del PAT enlazado.
    asgi_app = API_TOKEN_AUTH.wrap(asgi_app)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with pool, session_manager.run():
            await OAUTH_REDIS.ping()
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
                await OAUTH_REDIS.aclose()

    async def health(_request) -> JSONResponse:
        return JSONResponse({"ok": True, "service": "higpertext-mcp"})

    oauth_routes = create_auth_routes(
        provider=OAUTH_PROVIDER,
        issuer_url=ISSUER_URL,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["mcp"],
            default_scopes=["mcp"],
        ),
    )
    oauth_metadata = build_metadata(
        ISSUER_URL,
        None,
        ClientRegistrationOptions(enabled=True, valid_scopes=["mcp"], default_scopes=["mcp"]),
        RevocationOptions(enabled=True),
    )
    oauth_metadata.grant_types_supported = ["authorization_code", "refresh_token"]
    oauth_routes = [route for route in oauth_routes if route.path != "/.well-known/oauth-authorization-server"]
    resource_routes = create_protected_resource_routes(
        resource_url=RESOURCE_URL,
        authorization_servers=[ISSUER_URL],
        scopes_supported=["mcp"],
        resource_name="Higpertext MCP",
    )
    return Starlette(
        routes=[
            Route("/health", health),
            Route(
                "/.well-known/oauth-authorization-server",
                MetadataHandler(oauth_metadata).handle,
                methods=["GET"],
            ),
            *oauth_routes,
            *resource_routes,
            Route("/oauth/consent", OAUTH_PROVIDER.consent_page, methods=["GET"]),
            Route("/oauth/consent", OAUTH_PROVIDER.submit_consent, methods=["POST"]),
            Mount("/mcp", app=asgi_app),
        ],
        lifespan=lifespan,
        middleware=[
            Middleware(
                TrustedHostMiddleware,
                allowed_hosts=list({"127.0.0.1", "localhost", "testserver", PUBLIC_HOSTNAME}),
            ),
        ],
    )


app = build_app()

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
