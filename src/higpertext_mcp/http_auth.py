"""OAuth bearer de usuario para MCP HTTP, introspectado por rules-api."""

from __future__ import annotations

import asyncio
import contextvars
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from starlette.responses import JSONResponse

from higpertext_mcp import auth


@dataclass(frozen=True)
class ApiTokenContext:
    token_id: str
    user_id: str
    scopes: frozenset[str]
    profile: str
    organization_ids: frozenset[str]
    repository_ids: frozenset[str]
    project_ids: frozenset[str] = frozenset()
    organization_project_ids: dict[str, frozenset[str]] = field(default_factory=dict)


_current_token: contextvars.ContextVar[ApiTokenContext | None] = contextvars.ContextVar(
    "higpertext_api_token", default=None
)


def current_api_token() -> ApiTokenContext | None:
    return _current_token.get()


class ApiTokenAuth:
    """Autentica el PAT por introspección y lo aísla durante cada request MCP."""

    def __init__(
        self, app=None, *, api_url: str | None = None, provider=None, resource_metadata_url: str = ""
    ) -> None:
        self.app = app
        self.resource_metadata_url = resource_metadata_url
        self.api_url = (api_url or os.environ.get("HTX_RFC_API") or os.environ.get(
            "HTX_RULES_API_URL", "http://127.0.0.1:8080"
        )).rstrip("/")
        self.provider = provider or auth.default_provider()

    def wrap(self, app):
        self.app = app
        return self

    async def authenticate_pat(self, pat: str) -> ApiTokenContext | None:
        """Validate one API token, shared by MCP requests and OAuth consent."""
        return await self._authenticate(pat, "/api/tokens/introspect")

    async def authenticate_oauth(self, token: str) -> ApiTokenContext | None:
        return await self._authenticate(token, "/api/tokens/oauth/introspect")

    async def exchange_pat(self, pat: str, client_id: str) -> dict[str, Any] | None:
        return await self._service_request("/api/tokens/oauth/exchange", {"token": pat, "clientId": client_id})

    async def refresh_oauth(self, refresh_token: str, client_id: str) -> dict[str, Any] | None:
        return await self._service_request("/api/tokens/oauth/refresh", {"refreshToken": refresh_token, "clientId": client_id})

    async def revoke_oauth(self, token: str) -> None:
        await self._service_request("/api/tokens/oauth/revoke", {"token": token})

    async def _service_request(self, path: str, body: dict[str, Any]) -> dict[str, Any] | None:
        service_token = await self.provider.token()
        try:
            return await asyncio.to_thread(self._post_json, path, body, service_token)
        except urllib.error.HTTPError as exc:
            if exc.code == 401 and path.endswith("/refresh"):
                return None
            raise

    def _post_json(self, path: str, body: dict[str, Any], service_token: str) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.api_url}{path}", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {service_token}", "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 — URL de servicio configurada
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}

    def _introspect(self, pat: str, service_token: str, path: str) -> dict[str, Any]:
        body = json.dumps({"token": pat}).encode()
        request = urllib.request.Request(
            f"{self.api_url}{path}",
            data=body,
            headers={
                "Authorization": f"Bearer {service_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 — URL de servicio configurada
            return json.loads(response.read().decode("utf-8"))

    async def _authenticate(self, pat: str, path: str) -> ApiTokenContext | None:
        service_token = await self.provider.token()
        try:
            result = await asyncio.to_thread(self._introspect, pat, service_token, path)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                self.provider.invalidate()
                service_token = await self.provider.token()
                result = await asyncio.to_thread(self._introspect, pat, service_token, path)
            else:
                raise
        if result.get("active") is not True:
            return None
        return ApiTokenContext(
            token_id=str(result.get("id", "")),
            user_id=str(result.get("userId", "")),
            scopes=frozenset(str(item) for item in result.get("scopes", [])),
            profile=str(result.get("profile", "")),
            organization_ids=frozenset(str(item) for item in result.get("organizationIds", [])),
            repository_ids=frozenset(str(item) for item in result.get("repositoryIds", [])),
            project_ids=frozenset(str(item) for item in result.get("projectIds", [])),
            organization_project_ids={
                str(org_id): frozenset(str(project_id) for project_id in project_ids)
                for org_id, project_ids in (result.get("organizationProjectIds") or {}).items()
            },
        )

    async def __call__(self, scope, receive, send) -> None:
        authorization = next(
            (value for name, value in scope.get("headers", []) if name == b"authorization"),
            b"",
        )
        scheme, separator, credential = authorization.partition(b" ")
        if (
            not separator
            or scheme.lower() != b"bearer"
            or not credential.startswith(b"htx_oat_")
            or len(credential) > 512
        ):
            await self._reject(scope, receive, send, 401, "se requiere un token de API válido", self.resource_metadata_url)
            return
        try:
            oauth_token = credential.decode("ascii")
            token_context = await self.authenticate_oauth(oauth_token)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            token_context = None
        except (auth.AuthError, OSError, urllib.error.URLError, TimeoutError):
            await self._reject(scope, receive, send, 503, "no se pudo validar el token", self.resource_metadata_url)
            return
        if token_context is None:
            await self._reject(scope, receive, send, 401, "token inválido, vencido o revocado", self.resource_metadata_url)
            return
        marker = _current_token.set(token_context)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_token.reset(marker)

    @staticmethod
    async def _reject(scope, receive, send, status: int, message: str, resource_metadata_url: str = "") -> None:
        challenge = 'Bearer error="invalid_token"'
        if resource_metadata_url:
            challenge += f', resource_metadata="{resource_metadata_url}"'
        response = JSONResponse(
            {"error": message},
            status_code=status,
            headers={"WWW-Authenticate": challenge},
        )
        await response(scope, receive, send)
