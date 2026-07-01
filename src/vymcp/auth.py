"""Bearer-token verification for the hosted (http) transport.

Each request carries a ``vym_`` token; we validate it against VyManager and hand
back an AccessToken whose subject is a stable, token-derived id used to scope the
caller's pending plans. The raw token is carried through so tools can act as that
caller (VyManager still enforces the token's RBAC and records the real user).
"""

from __future__ import annotations

import hashlib
import time

from mcp.server.auth.provider import AccessToken, TokenVerifier

from .client import VyManagerClient
from .config import ServerConfig

# A cheap authenticated endpoint: 200 = valid token, 401 = not.
_VALIDATE_PATH = "/session/sites"
_CACHE_TTL_SECONDS = 60.0


class VyManagerTokenVerifier(TokenVerifier):
    def __init__(self, server_config: ServerConfig) -> None:
        self._server_config = server_config
        self._cache: dict[str, tuple[float, AccessToken]] = {}

    async def verify_token(self, token: str) -> AccessToken | None:
        now = time.monotonic()
        cached = self._cache.get(token)
        if cached and cached[0] > now:
            return cached[1]

        client = VyManagerClient(self._server_config.client_config(token))
        try:
            await client.get(_VALIDATE_PATH)
        except Exception:
            return None
        finally:
            await client.aclose()

        subject = "vym_" + hashlib.sha256(token.encode()).hexdigest()[:16]
        access = AccessToken(token=token, client_id=subject, scopes=[], subject=subject)
        self._cache[token] = (now + _CACHE_TTL_SECONDS, access)
        return access
