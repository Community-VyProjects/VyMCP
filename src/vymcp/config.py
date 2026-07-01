"""Environment-based configuration for VyMCP."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

_FALSEY = {"0", "false", "no", "off"}
_TRUTHY = {"1", "true", "yes", "on"}


def writes_enabled() -> bool:
    """Whether configuration-changing tools are enabled (off by default).

    This is the operator kill-switch, independent of the token's own scope: even
    a read-write token cannot change config unless writes are explicitly enabled.
    """
    return os.environ.get("VYMANAGER_ENABLE_WRITES", "false").strip().lower() in _TRUTHY


def _verify_ssl() -> bool:
    return os.environ.get("VYMANAGER_VERIFY_SSL", "true").lower() not in _FALSEY


def _timeout() -> float:
    try:
        return float(os.environ.get("VYMANAGER_TIMEOUT", "30"))
    except ValueError:
        return 30.0


@dataclass(frozen=True)
class Config:
    """Per-client config: everything needed to talk to VyManager as one token."""

    base_url: str
    api_token: str
    verify_ssl: bool = True
    timeout: float = 30.0


@dataclass(frozen=True)
class ServerConfig:
    """Server-level config. In http mode the token arrives per request, so
    ``api_token`` is only required for stdio (single-tenant, local) mode."""

    base_url: str
    verify_ssl: bool = True
    timeout: float = 30.0
    transport: str = "stdio"  # "stdio" or "http"
    host: str = "127.0.0.1"
    port: int = 8080
    public_url: str = "http://127.0.0.1:8080"  # externally reachable URL (http mode)
    api_token: str | None = None
    # Host header values the http server accepts (DNS-rebinding protection). Empty
    # tuple means allow any host (protection disabled).
    allowed_hosts: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_env(cls) -> ServerConfig:
        base_url = os.environ.get("VYMANAGER_BASE_URL")
        if not base_url:
            raise RuntimeError("Missing required environment variable: VYMANAGER_BASE_URL.")

        transport = os.environ.get("VYMCP_TRANSPORT", "stdio").strip().lower()
        if transport not in {"stdio", "http"}:
            raise RuntimeError(f"VYMCP_TRANSPORT must be 'stdio' or 'http', got '{transport}'.")

        api_token = os.environ.get("VYMANAGER_API_TOKEN")
        if transport == "stdio" and not api_token:
            raise RuntimeError(
                "VYMANAGER_API_TOKEN is required for stdio transport. "
                "(In http mode, clients present their own token per request.)"
            )

        try:
            port = int(os.environ.get("VYMCP_PORT", "8080"))
        except ValueError:
            port = 8080

        host = os.environ.get("VYMCP_HOST", "127.0.0.1")
        public_url = os.environ.get("VYMCP_PUBLIC_URL") or f"http://{host}:{port}"
        public_url = public_url.rstrip("/")

        # Which Host headers the http server accepts. Explicit override wins;
        # otherwise default to the public URL's host:port so external clients that
        # reach the server at its advertised address are allowed. "*" disables the
        # DNS-rebinding check entirely (use only behind a trusted proxy).
        allowed_env = os.environ.get("VYMCP_ALLOWED_HOSTS", "").strip()
        if allowed_env == "*":
            allowed_hosts: tuple[str, ...] = ()
        elif allowed_env:
            allowed_hosts = tuple(h.strip() for h in allowed_env.split(",") if h.strip())
        else:
            netloc = urlparse(public_url).netloc
            allowed_hosts = (netloc,) if netloc else ()

        return cls(
            base_url=base_url.rstrip("/"),
            verify_ssl=_verify_ssl(),
            timeout=_timeout(),
            transport=transport,
            host=host,
            port=port,
            public_url=public_url,
            api_token=api_token,
            allowed_hosts=allowed_hosts,
        )

    def client_config(self, token: str) -> Config:
        """Build a per-client Config for a specific token."""
        return Config(
            base_url=self.base_url,
            api_token=token,
            verify_ssl=self.verify_ssl,
            timeout=self.timeout,
        )
