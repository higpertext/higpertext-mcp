"""OAuth authorization-code bridge for existing Higpertext API tokens.

The browser asks the user to authorize an existing PAT. The MCP client receives
short-lived OAuth credentials; rules-api resolves their access and permissions
through the linked PAT on every request.
"""

from __future__ import annotations

import html
import secrets
import time
from urllib.parse import urlencode

from pydantic import AnyHttpUrl, BaseModel
from redis.asyncio import Redis
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from higpertext_mcp.http_auth import ApiTokenAuth


class _AuthorizationRequest(BaseModel):
    client_id: str
    params: AuthorizationParams
    expires_at: int


class PATAuthorizationCode(AuthorizationCode):
    pat: str


class PATOAuthProvider(
    OAuthAuthorizationServerProvider[PATAuthorizationCode, RefreshToken, AccessToken]
):
    """Persist OAuth clients and short-lived grants in Redis."""

    def __init__(self, redis: Redis, api_auth: ApiTokenAuth, issuer_url: str) -> None:
        self.redis = redis
        self.api_auth = api_auth
        self.issuer_url = issuer_url.rstrip("/")

    @staticmethod
    def _key(kind: str, identifier: str) -> str:
        return f"higpertext:mcp-oauth:{kind}:{identifier}"

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        value = await self.redis.get(self._key("client", client_id))
        return OAuthClientInformationFull.model_validate_json(value) if value else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if not client_info.client_id:
            raise ValueError("OAuth client registration did not assign a client ID")
        await self.redis.set(
            self._key("client", client_info.client_id),
            client_info.model_dump_json(exclude_none=True),
        )

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        if params.scopes and not set(params.scopes).issubset({"mcp"}):
            raise AuthorizeError("invalid_scope", "El MCP solo admite el alcance OAuth 'mcp'.")
        if params.resource and not self._valid_resource(params.resource):
            raise AuthorizeError("invalid_request", "El recurso solicitado no corresponde a este MCP.")
        transaction_id = secrets.token_urlsafe(32)
        transaction = _AuthorizationRequest(
            client_id=str(client.client_id), params=params, expires_at=int(time.time()) + 600
        )
        await self.redis.set(
            self._key("transaction", transaction_id),
            transaction.model_dump_json(),
            ex=600,
        )
        return f"{self.issuer_url}/oauth/consent?{urlencode({'transaction': transaction_id})}"

    def _valid_resource(self, resource: str) -> bool:
        return resource.rstrip("/") == f"{self.issuer_url}/mcp"

    async def consent_page(self, request: Request) -> Response:
        transaction_id = request.query_params.get("transaction", "")
        if not transaction_id or len(transaction_id) > 128:
            return HTMLResponse(_page("Enlace de autorización inválido", "Vuelve al cliente MCP e inténtalo de nuevo."), status_code=400)
        value = await self.redis.get(self._key("transaction", transaction_id))
        if not value:
            return HTMLResponse(_page("Autorización vencida", "Vuelve al cliente MCP para iniciar una nueva autorización."), status_code=400)
        transaction = _AuthorizationRequest.model_validate_json(value)
        client = await self.get_client(transaction.client_id)
        client_name = html.escape((client.client_name if client else None) or "cliente MCP")
        return HTMLResponse(
            _consent_form(transaction_id, client_name),
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"},
        )

    async def submit_consent(self, request: Request) -> Response:
        form = await request.form()
        transaction_id = str(form.get("transaction", ""))
        pat = str(form.get("pat", ""))
        approved = form.get("approve") == "yes"
        if not transaction_id or len(transaction_id) > 128 or len(pat) > 512 or not pat.startswith("htx_pat_"):
            return HTMLResponse(_page("No se pudo autorizar", "Revisa el formulario e inténtalo de nuevo."), status_code=400)
        key = self._key("transaction", transaction_id)
        raw = await self.redis.get(key)
        if not raw:
            return HTMLResponse(_page("Autorización vencida", "Vuelve al cliente MCP para iniciar una nueva autorización."), status_code=400)
        transaction = _AuthorizationRequest.model_validate_json(raw)
        if transaction.expires_at < int(time.time()):
            await self.redis.delete(key)
            return HTMLResponse(_page("Autorización vencida", "Vuelve al cliente MCP para iniciar una nueva autorización."), status_code=400)
        if not approved:
            await self.redis.delete(key)
            return self._redirect_error(transaction, "access_denied")
        try:
            context = await self.api_auth.authenticate_pat(pat)
        except Exception:
            return HTMLResponse(
                _consent_form(transaction_id, "cliente MCP", "No se pudo validar el token. Inténtalo de nuevo."),
                status_code=503,
                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
            )
        if context is None:
            return HTMLResponse(
                _consent_form(transaction_id, "cliente MCP", "El PAT no es válido, está vencido o fue revocado."),
                status_code=401,
                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
            )

        # Consume the transaction only after validation, and only once.
        consumed = await self.redis.getdel(key)
        if consumed != raw:
            return HTMLResponse(_page("Autorización ya procesada", "Vuelve al cliente MCP para iniciar una nueva autorización."), status_code=409)
        code_value = secrets.token_urlsafe(32)
        code = PATAuthorizationCode(
            code=code_value,
            scopes=["mcp"],
            expires_at=time.time() + 120,
            client_id=transaction.client_id,
            code_challenge=transaction.params.code_challenge,
            redirect_uri=transaction.params.redirect_uri,
            redirect_uri_provided_explicitly=transaction.params.redirect_uri_provided_explicitly,
            resource=transaction.params.resource,
            subject=context.user_id,
            pat=pat,
        )
        await self.redis.set(self._key("code", code_value), code.model_dump_json(), ex=120)
        query: dict[str, str] = {"code": code_value}
        if transaction.params.state is not None:
            query["state"] = transaction.params.state
        target = construct_redirect_uri(str(transaction.params.redirect_uri), **query)
        return RedirectResponse(target, status_code=302, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    def _redirect_error(self, transaction: _AuthorizationRequest, error: str) -> Response:
        query = {"error": error}
        if transaction.params.state is not None:
            query["state"] = transaction.params.state
        return RedirectResponse(
            construct_redirect_uri(str(transaction.params.redirect_uri), **query),
            status_code=302,
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> PATAuthorizationCode | None:
        raw = await self.redis.get(self._key("code", authorization_code))
        if not raw:
            return None
        code = PATAuthorizationCode.model_validate_json(raw)
        return code if code.client_id == client.client_id else None

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: PATAuthorizationCode
    ) -> OAuthToken:
        raw = await self.redis.getdel(self._key("code", authorization_code.code))
        if not raw:
            raise TokenError("invalid_grant", "El código ya fue utilizado o venció.")
        stored = PATAuthorizationCode.model_validate_json(raw)
        if stored.client_id != client.client_id or stored.pat != authorization_code.pat:
            raise TokenError("invalid_grant", "El código de autorización no es válido.")
        try:
            tokens = await self.api_auth.exchange_pat(stored.pat, str(client.client_id))
        except Exception as exc:
            raise TokenError("server_error", "No se pudo emitir la sesión OAuth.") from exc
        if not tokens or not tokens.get("access_token") or not tokens.get("refresh_token"):
            raise TokenError("invalid_grant", "El PAT venció o fue revocado.")
        return OAuthToken(
            access_token=str(tokens["access_token"]),
            token_type="Bearer",
            expires_in=int(tokens.get("expires_in", 600)),
            refresh_token=str(tokens["refresh_token"]),
            scope="mcp",
        )

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        if not refresh_token.startswith("htx_ort_"):
            return None
        return RefreshToken(token=refresh_token, client_id=str(client.client_id), scopes=["mcp"], subject="")

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        if scopes and not set(scopes).issubset({"mcp"}):
            raise TokenError("invalid_scope", "El MCP solo admite el alcance OAuth 'mcp'.")
        tokens = await self.api_auth.refresh_oauth(refresh_token.token, str(client.client_id))
        if not tokens or not tokens.get("access_token") or not tokens.get("refresh_token"):
            raise TokenError("invalid_grant", "La autorización venció o el PAT fue revocado.")
        return OAuthToken(
            access_token=str(tokens["access_token"]), token_type="Bearer",
            expires_in=int(tokens.get("expires_in", 600)),
            refresh_token=str(tokens["refresh_token"]), scope="mcp",
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        context = await self.api_auth.authenticate_oauth(token)
        if context is None:
            return None
        return AccessToken(token=token, client_id="higpertext-mcp", scopes=["mcp"], subject=context.user_id)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        # Revoca solo el grant OAuth; el PAT se conserva para otros clientes.
        await self.api_auth.revoke_oauth(token.token)


def _page(title: str, message: str) -> str:
    return f"""<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>{html.escape(title)}</title><body style="font:16px system-ui;max-width:34rem;margin:12vh auto;padding:1.5rem;color-scheme:light dark"><main><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p></main></body></html>"""


def _consent_form(transaction: str, client_name: str, error: str = "") -> str:
    error_html = f'<p role="alert" style="color:#a21d2e">{html.escape(error)}</p>' if error else ""
    return f"""<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>Autorizar Higpertext MCP</title><body style="font:16px system-ui;max-width:34rem;margin:8vh auto;padding:1.5rem;color-scheme:light dark"><main><h1>Autorizar Higpertext MCP</h1><p><b>{client_name}</b> solicita acceso a tus herramientas MCP.</p><p>Se aplicarán los permisos y el alcance de organizaciones/repositorios ya configurados en tu PAT. Puedes revocar el PAT desde Tokens de API.</p>{error_html}<form method="post" action="/oauth/consent"><input type="hidden" name="transaction" value="{html.escape(transaction, quote=True)}"><label for="pat">Token de API</label><input id="pat" name="pat" type="password" autocomplete="off" autocapitalize="none" spellcheck="false" required style="display:block;box-sizing:border-box;width:100%;margin:.5rem 0 1rem;padding:.8rem"><label style="display:flex;gap:.5rem;align-items:flex-start;margin:1rem 0"><input type="checkbox" name="approve" value="yes" required><span>Autorizo a este cliente a usar Higpertext MCP con los permisos de este token.</span></label><button type="submit">Autorizar</button></form><p style="font-size:.85rem">El PAT se envía a rules-api para validarlo y no queda guardado en el navegador.</p></main></body></html>"""

