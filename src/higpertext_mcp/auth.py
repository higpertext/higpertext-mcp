"""Autenticación del agente contra Keycloak (OIDC client_credentials).

El agente actúa con su propia cuenta de servicio (client confidential con service
account), no con la identidad de una persona: la bitácora distingue quién hizo qué
y no hace falta abrir el login directo de ningún client público. El token es de
vida corta, vive solo en memoria y se renueva antes de expirar; nada se escribe a
disco. El secreto sale de `config.agent_client_secret()` (env o archivo) y jamás
aparece en logs ni en mensajes de error.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from higpertext_mcp import config

_REQUEST_TIMEOUT_S = 5.0
_SKEW_S = 30.0  # renovar un poco antes de que expire


class AuthError(RuntimeError):
    """No se pudo obtener un token. El mensaje es apto para mostrar al usuario."""


Fetch = Callable[[str, dict[str, str]], dict[str, Any]]


def _http_fetch(url: str, form: dict[str, str]) -> dict[str, Any]:
    headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
    if host := config.oidc_host_header():
        headers["Host"] = host
    request = urllib.request.Request(
        url, data=urllib.parse.urlencode(form).encode(), headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_S) as response:  # noqa: S310 — URL de config propia
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        code = ""
        try:
            code = str(json.loads(exc.read().decode()).get("error", ""))
        except (ValueError, OSError):
            pass
        raise AuthError(_describe_http_failure(exc.code, code)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise AuthError(
            f"Keycloak no responde en {url}. Verifica que esté arriba "
            "(docker ps --filter name=keycloak) y que HIGPERTEXT_OIDC_TOKEN_URL sea correcta."
        ) from None
    except ValueError:
        raise AuthError("Keycloak devolvió una respuesta que no es JSON válido.") from None


def _describe_http_failure(status: int, error_code: str) -> str:
    if error_code == "invalid_client" or status == 401:
        return (
            "Keycloak rechazó las credenciales del agente (invalid_client): revisa "
            "HIGPERTEXT_AGENT_CLIENT_ID y HIGPERTEXT_AGENT_CLIENT_SECRET."
        )
    if error_code == "unauthorized_client":
        return "El client del agente no tiene habilitada la cuenta de servicio (service account) en Keycloak."
    return f"Keycloak rechazó la solicitud de token (HTTP {status}{', ' + error_code if error_code else ''})."


class ServiceTokenProvider:
    """Obtiene y cachea el access token de la cuenta de servicio del agente."""

    def __init__(
        self,
        *,
        token_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        fetch: Fetch | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._fetch = fetch or _http_fetch
        self._clock = clock
        self._token = ""
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    def _valid(self) -> bool:
        return bool(self._token) and self._clock() < self._expires_at - _SKEW_S

    def invalidate(self) -> None:
        """Descarta el token cacheado (p. ej. tras un 401 de la API)."""
        self._token = ""
        self._expires_at = 0.0

    async def token(self) -> str:
        if self._valid():
            return self._token
        async with self._lock:
            if self._valid():  # otra corrutina renovó mientras esperábamos
                return self._token
            client_id = self._client_id or config.agent_client_id()
            secret = self._client_secret if self._client_secret is not None else config.agent_client_secret()
            if not secret:
                raise AuthError(
                    "Falta el secreto del agente: define HIGPERTEXT_AGENT_CLIENT_SECRET "
                    "(o HIGPERTEXT_AGENT_CLIENT_SECRET_FILE)."
                )
            url = self._token_url or config.oidc_token_url()
            body = await asyncio.to_thread(
                self._fetch, url,
                {"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret},
            )
            token = body.get("access_token")
            if not isinstance(token, str) or not token:
                raise AuthError("Keycloak no devolvió access_token.")
            expires_in = body.get("expires_in")
            self._token = token
            self._expires_at = self._clock() + (float(expires_in) if isinstance(expires_in, (int, float)) else 60.0)
            return token

    async def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self.token()}"}


_default: ServiceTokenProvider | None = None


def default_provider() -> ServiceTokenProvider:
    global _default
    if _default is None:
        _default = ServiceTokenProvider()
    return _default
