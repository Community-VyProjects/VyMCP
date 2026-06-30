"""Async HTTP client for the VyManager API.

VyMCP never talks to VyOS directly — every call goes through VyManager so that
authentication, RBAC, audit, and commit-confirm stay enforced in one place.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Config

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


_client: VyManagerClient | None = None


def get_client() -> VyManagerClient:
    """Lazily build a shared VyManager client from the environment on first use."""
    global _client
    if _client is None:
        config = Config.from_env()
        logger.info("Connecting to VyManager at %s", config.base_url)
        _client = VyManagerClient(config)
    return _client


def set_client(client: VyManagerClient | None) -> None:
    """Override the shared client (used by tests)."""
    global _client
    _client = client


async def close_client() -> None:
    """Close the shared client on shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
