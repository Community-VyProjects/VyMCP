"""Async HTTP client for the VyManager API.

VyMCP never talks to VyOS directly — every call goes through VyManager so that
authentication, RBAC, audit, and commit-confirm stay enforced in one place.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .config import Config


class VyManagerError(Exception):
    """Raised when a VyManager request fails. The message is safe to show a user."""


class VyManagerClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={"Authorization": f"Bearer {config.api_token}"},
            verify=config.verify_ssl,
            timeout=config.timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(
        self,
        path: str,
        *,
        instance_id: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        headers = {}
        if instance_id:
            headers["X-VyOS-Instance-Id"] = instance_id

        try:
            response = await self._client.get(path, headers=headers, params=params)
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
    def _explain_error(response: httpx.Response, instance_id: Optional[str]) -> str:
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
            return f"{base} The token may be read-only or lack permission for this feature/instance."
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
