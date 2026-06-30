"""Environment-based configuration for VyMCP."""

from __future__ import annotations

import os
from dataclasses import dataclass

_FALSEY = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class Config:
    base_url: str
    api_token: str
    verify_ssl: bool = True
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "Config":
        base_url = os.environ.get("VYMANAGER_BASE_URL")
        api_token = os.environ.get("VYMANAGER_API_TOKEN")

        missing = [
            name
            for name, value in (
                ("VYMANAGER_BASE_URL", base_url),
                ("VYMANAGER_API_TOKEN", api_token),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + ". See .env.example."
            )

        verify_ssl = os.environ.get("VYMANAGER_VERIFY_SSL", "true").lower() not in _FALSEY
        try:
            timeout = float(os.environ.get("VYMANAGER_TIMEOUT", "30"))
        except ValueError:
            timeout = 30.0

        return cls(
            base_url=base_url.rstrip("/"),
            api_token=api_token,
            verify_ssl=verify_ssl,
            timeout=timeout,
        )
