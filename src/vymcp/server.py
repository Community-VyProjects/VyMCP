"""VyMCP server — read-only MCP tools over the VyManager API.

Phase 1: instance discovery plus version-aware capabilities and normalized
configuration for every VyManager feature. All tools are read-only.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .client import VyManagerClient
from .config import Config
from .features import FEATURES, resolve_feature

mcp = FastMCP("VyMCP")

_client: Optional[VyManagerClient] = None


def _get_client() -> VyManagerClient:
    """Lazily build the VyManager client from the environment on first use."""
    global _client
    if _client is None:
        _client = VyManagerClient(Config.from_env())
    return _client


@mcp.tool()
async def list_instances() -> list[dict[str, Any]]:
    """List the VyOS instances this token can access.

    Returns each instance's ``instance_id`` (pass it to other tools), name, site,
    host, VyOS version, and whether it is active.
    """
    client = _get_client()
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
    return await _get_client().get(
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
    return await _get_client().get(
        f"/vyos/{resolved.slug}/config", instance_id=instance_id
    )


def main() -> None:
    """Console-script entry point. Runs the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
