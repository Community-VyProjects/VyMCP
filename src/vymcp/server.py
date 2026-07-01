"""VyMCP server — read-only MCP tools over the VyManager API.

Phase 1: instance discovery plus version-aware capabilities and normalized
configuration for every VyManager feature. All tools are read-only.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import close_client, current_client
from .features import FEATURES, resolve_feature
from .writes import register_write_tools


@asynccontextmanager
async def _lifespan(_server: FastMCP):
    """Ensure the shared HTTP client is closed cleanly on shutdown."""
    try:
        yield {}
    finally:
        await close_client()


mcp = FastMCP("VyMCP", lifespan=_lifespan)


@mcp.tool()
async def list_instances() -> list[dict[str, Any]]:
    """List the VyOS instances this token can access.

    Returns each instance's ``instance_id`` (pass it to other tools), name, site,
    host, VyOS version, and whether it is active.
    """
    client = current_client()
    sites = await client.get("/session/sites")

    instances: list[dict[str, Any]] = []
    for site in sites:
        site_instances = await client.get(f"/session/sites/{site['id']}/instances")
        for inst in site_instances:
            instances.append(
                {
                    "instance_id": inst["id"],
                    "name": inst.get("name"),
                    "site": site.get("name"),
                    "host": inst.get("host"),
                    "vyos_version": inst.get("vyos_version"),
                    "is_active": inst.get("is_active"),
                }
            )
    return instances


@mcp.tool()
def list_features() -> list[dict[str, str]]:
    """List the VyOS configuration features VyMCP can read.

    Use the returned ``feature`` slug with get_capabilities and get_config.
    """
    return [{"feature": f.slug, "description": f.description} for f in FEATURES]


@mcp.tool()
async def get_capabilities(feature: str, instance_id: str) -> dict[str, Any]:
    """Version-aware capability flags for a feature on a specific instance.

    Args:
        feature: A feature slug from list_features (e.g. "nat", "firewall/ipv4").
        instance_id: An instance_id from list_instances.
    """
    resolved = resolve_feature(feature)
    return await current_client().get(
        f"/vyos/{resolved.slug}/capabilities", instance_id=instance_id
    )


@mcp.tool()
async def get_config(feature: str, instance_id: str) -> dict[str, Any]:
    """Normalized configuration for a feature on a specific instance.

    Args:
        feature: A feature slug from list_features (e.g. "nat", "firewall/ipv4").
        instance_id: An instance_id from list_instances.
    """
    resolved = resolve_feature(feature)
    return await current_client().get(
        f"/vyos/{resolved.slug}/config", instance_id=instance_id
    )


# Change tools are registered only when VYMANAGER_ENABLE_WRITES is set; a
# read-only deployment exposes the four read tools above and nothing else.
register_write_tools(mcp)


def main() -> None:
    """Console-script entry point. Runs stdio or a hosted http server per config."""
    from .client import server_config

    config = server_config()
    if config.transport == "http":
        from mcp.server.auth.settings import AuthSettings
        from mcp.server.transport_security import TransportSecuritySettings

        from .auth import VyManagerTokenVerifier

        mcp.settings.host = config.host
        mcp.settings.port = config.port
        # FastMCP auto-configures DNS-rebinding protection for localhost at
        # construction time (allowing only 127.0.0.1/localhost). Since we bind and
        # advertise a different address in http mode, replace it with an allowlist
        # derived from config, or disable it when no hosts are configured.
        if config.allowed_hosts:
            origins = [f"{scheme}://{h}" for h in config.allowed_hosts for scheme in ("http", "https")]
            mcp.settings.transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=list(config.allowed_hosts),
                allowed_origins=origins,
            )
        else:
            mcp.settings.transport_security = TransportSecuritySettings(
                enable_dns_rebinding_protection=False,
            )
        mcp.settings.auth = AuthSettings(
            issuer_url=config.base_url,  # type: ignore[arg-type]  # pydantic coerces str->AnyHttpUrl
            resource_server_url=config.public_url,  # type: ignore[arg-type]
        )
        mcp._token_verifier = VyManagerTokenVerifier(config)
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
