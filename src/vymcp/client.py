"""Async HTTP client for the VyManager API.

VyMCP never talks to VyOS directly — every call goes through VyManager so that
authentication, RBAC, audit, and commit-confirm stay enforced in one place.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Config, ServerConfig

logger = logging.getLogger("vymcp")


class VyManagerError(Exception):
    """Raised when a VyManager request fails. The message is safe to show a user."""


class VyManagerClient:
    def __init__(
        self,
        config: Config,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        # `transport` is injected by tests (httpx.MockTransport); production leaves it None.
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={"Authorization": f"Bearer {config.api_token}"},
            verify=config.verify_ssl,
            timeout=config.timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(
        self,
        path: str,
        *,
        instance_id: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request("GET", path, instance_id=instance_id, params=params)

    async def post(
        self,
        path: str,
        *,
        instance_id: str | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request("POST", path, instance_id=instance_id, json=json)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        instance_id: str | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        headers = {}
        if instance_id:
            headers["X-VyOS-Instance-Id"] = instance_id

        try:
            response = await self._client.request(
                method, path, headers=headers, params=params, json=json
            )
        except httpx.RequestError as exc:
            raise VyManagerError(
                f"Could not reach VyManager at {self._config.base_url}: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise VyManagerError(self._explain_error(response, instance_id))

        try:
            return response.json()
        except ValueError as exc:
            raise VyManagerError("VyManager returned a non-JSON response.") from exc

    @staticmethod
    def _explain_error(response: httpx.Response, instance_id: str | None) -> str:
        detail = None
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("detail") or body.get("error")
        except ValueError:
            detail = None

        status = response.status_code
        if status == 401:
            return "VyManager rejected the API token (401). It may be invalid, expired, or revoked."
        if status == 403:
            base = "VyManager denied the request (403)."
            if detail:
                return f"{base} {detail}"
            return (
                f"{base} The token may be read-only or lack permission for this "
                "feature/instance."
            )
        if status == 404:
            if not instance_id:
                return (
                    "No target instance selected (404). Pass an instance_id from list_instances."
                )
            return (
                f"VyManager could not serve this request for instance '{instance_id}' (404). "
                "The instance may not exist or the token may not be scoped to reach it."
            )

        return f"VyManager request failed ({status})." + (f" {detail}" if detail else "")


_server_config: ServerConfig | None = None
_clients: dict[str, VyManagerClient] = {}
_override: VyManagerClient | None = None  # test hook


def server_config() -> ServerConfig:
    global _server_config
    if _server_config is None:
        _server_config = ServerConfig.from_env()
        logger.info(
            "VyManager %s (%s transport)", _server_config.base_url, _server_config.transport
        )
    return _server_config


def _current_token() -> str:
    """The token for the current request: the caller's bearer token in http mode,
    or the server's env token in stdio mode."""
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token

        access = get_access_token()
    except Exception:
        access = None
    if access is not None:
        return access.token

    token = server_config().api_token
    if not token:
        raise VyManagerError("No API token available for this request.")
    return token


def current_client() -> VyManagerClient:
    """The VyManager client for the current request's identity.

    In http mode each caller's token gets its own (cached) client; in stdio mode
    there is a single env-token client. Tests can override via set_client().
    """
    if _override is not None:
        return _override
    token = _current_token()
    if token not in _clients:
        _clients[token] = VyManagerClient(server_config().client_config(token))
    return _clients[token]


def current_owner() -> str:
    """A stable identity for the current caller, used to scope pending plans."""
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token

        access = get_access_token()
    except Exception:
        access = None
    if access is not None and access.subject:
        return access.subject
    return "local"


def set_client(client: VyManagerClient | None) -> None:
    """Override the client for all requests (used by tests)."""
    global _override
    _override = client


async def close_client() -> None:
    """Close all cached clients on shutdown."""
    global _override
    for client in list(_clients.values()):
        await client.aclose()
    _clients.clear()
    if _override is not None:
        await _override.aclose()
        _override = None
