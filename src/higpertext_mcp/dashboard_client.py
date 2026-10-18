"""Cliente REST de los dashboards de rules-api.

Los dashboards viven en ``dashboards.db`` de rules-api (REST), no en el profile
server: no hay servicio gRPC ni cambio de proto. El MCP llama con el bearer de su
cuenta de servicio de Keycloak (el mismo que usa ``http_auth`` para introspectar
PATs) y la cabecera ``X-Htx-On-Behalf-Of`` con el ``user_id`` del PAT ya validado,
de modo que rules-api evalúa dueño, roles y permisos como si fuera esa persona. La
cabecera solo la sale de ``ApiTokenContext.user_id``, nunca de los argumentos de una
tool, y el PAT del cliente jamás se reenvía.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from higpertext_mcp import auth

DELEGATION_HEADER = "X-Htx-On-Behalf-Of"
API_PREFIX = "/api/dashboards"
DEFAULT_TIMEOUT_S = 10.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_MESSAGE = 300

# Un segmento de ruta es un id de dashboard, un nombre de plantilla o un número de versión.
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_BEHALF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")

_DEFAULT_CODES = {
    400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
    405: "method_not_allowed", 409: "conflict", 413: "too_large",
}


class DashboardError(RuntimeError):
    """Base de los errores del cliente. El mensaje nunca contiene secretos."""


class DashboardClientError(DashboardError, ValueError):
    """Argumento inválido detectado antes de hacer cualquier request."""

    code = "invalid_argument"


class DashboardApiError(DashboardError):
    """rules-api respondió con un error (o con algo que el cliente no acepta)."""

    def __init__(self, status: int, code: str, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.payload = payload or {}


class DashboardUnavailable(DashboardError):
    """rules-api (o Keycloak) no respondió: ``code`` es ``unavailable`` o ``timeout``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Un 3xx nunca se sigue: llevaría el bearer de servicio a otro destino."""

    def redirect_request(self, *_args, **_kwargs):  # noqa: D401 — firma del handler
        return None


def _base_url() -> str:
    # Misma convención que http_auth.ApiTokenAuth.
    return (os.environ.get("HTX_RFC_API") or os.environ.get("HTX_RULES_API_URL", "http://127.0.0.1:8080")).rstrip("/")


def _redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return _BEARER.sub("Bearer [redacted]", text)


class DashboardClient:
    """Una instancia por llamada de la tool: no cachea nada a nivel de módulo."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        provider: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
    ) -> None:
        self._base_url = (base_url or _base_url()).rstrip("/")
        self._provider = provider
        self._timeout = timeout
        self._max_bytes = max_response_bytes

    @staticmethod
    def _path(segments: tuple[str | int, ...]) -> str:
        path = API_PREFIX
        for segment in segments:
            text = str(segment)
            if isinstance(segment, bool) or not _SEGMENT.match(text):
                raise DashboardClientError(f"identificador inválido en la ruta: {text[:40]!r}")
            path += "/" + urllib.parse.quote(text, safe="")
        return path

    async def request(
        self,
        method: str,
        *segments: str | int,
        on_behalf_of: str,
        query: dict[str, str] | None = None,
        body: Any = None,
    ) -> Any:
        """Ejecuta un request y devuelve el JSON de la respuesta (``None`` si no hay cuerpo)."""
        if not isinstance(on_behalf_of, str) or not _BEHALF.match(on_behalf_of):
            raise DashboardClientError("se requiere el user_id del PAT validado para actuar en su nombre")
        path = self._path(segments)
        url = self._base_url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        payload = None if body is None else json.dumps(body).encode()
        provider = self._provider or auth.default_provider()

        for attempt in (1, 2):
            try:
                token = await provider.token()
            except auth.AuthError as exc:
                raise DashboardUnavailable("auth_unavailable", str(exc)) from None
            try:
                return await asyncio.to_thread(self._send, method, url, token, on_behalf_of, payload)
            except DashboardApiError as exc:
                if exc.status == 401 and attempt == 1:
                    provider.invalidate()
                    continue
                raise
        raise AssertionError("inalcanzable")  # pragma: no cover

    def _send(self, method: str, url: str, token: str, on_behalf_of: str, payload: bytes | None) -> Any:
        headers = {
            "Authorization": f"Bearer {token}",
            DELEGATION_HEADER: on_behalf_of,
            "Accept": "application/json",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=payload, headers=headers, method=method)
        opener = urllib.request.build_opener(_NoRedirect)
        secrets = [token]
        try:
            with opener.open(request, timeout=self._timeout) as response:  # noqa: S310 — URL de servicio configurada
                raw = self._read(response, response.status)
                return self._parse(response.status, raw, secrets)
        except urllib.error.HTTPError as exc:
            try:
                raw = self._read(exc, exc.code)
            finally:
                exc.close()
            raise self._api_error(exc.code, raw, secrets) from None
        except (TimeoutError, socket.timeout):
            raise DashboardUnavailable("timeout", "rules-api no respondió a tiempo.") from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise DashboardUnavailable("timeout", "rules-api no respondió a tiempo.") from None
            raise DashboardUnavailable("unavailable", "No se pudo conectar con rules-api.") from None
        except OSError:
            raise DashboardUnavailable("unavailable", "No se pudo conectar con rules-api.") from None

    def _read(self, response: Any, status: int) -> bytes:
        raw = response.read(self._max_bytes + 1)
        if len(raw) > self._max_bytes:
            raise DashboardApiError(status, "response_too_large", f"La respuesta de rules-api supera {self._max_bytes} bytes.")
        return raw

    @staticmethod
    def _parse(status: int, raw: bytes, secrets: list[str]) -> Any:
        if not raw.strip():
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise DashboardApiError(status, "invalid_response", "rules-api devolvió una respuesta que no es JSON.") from None

    @staticmethod
    def _api_error(status: int, raw: bytes, secrets: list[str]) -> DashboardApiError:
        text = raw.decode("utf-8", errors="replace").strip()
        code = _DEFAULT_CODES.get(status) or ("server_error" if status >= 500 else "http_error")
        if 300 <= status < 400:
            code = "unexpected_redirect"
        message = text
        payload: dict[str, Any] = {}
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            # Se vuelve a serializar ya redactado: el payload tampoco puede filtrar secretos.
            payload = json.loads(_redact(json.dumps(parsed), secrets))
            detail = payload.get("error")
            if isinstance(detail, dict):
                code = str(detail.get("code") or code)
                message = str(detail.get("message") or "")
            elif isinstance(detail, str):
                message = detail
            else:
                message = ""
        message = _redact(message, secrets)[:_MAX_MESSAGE] or f"rules-api respondió {status}"
        return DashboardApiError(status, code, message, payload)
