"""Registry of VyManager configuration features VyMCP can read.

Each slug maps to VyManager's ``/vyos/<slug>/capabilities`` and
``/vyos/<slug>/config`` endpoints. Kept in sync with VyManager's feature routers.
"""

from __future__ import annotations

from dataclasses import dataclass

# Feature slugs as they appear after /vyos/ in the VyManager API.
_SLUGS: tuple[str, ...] = (
    "access-list", "as-path-list", "babel", "bfd", "bgp", "bonding", "bridge",
    "broadcast-relay", "community-list", "config-sync", "conntrack-sync",
    "console-server", "container", "dhcp", "dhcp-relay", "dhcpv6-relay",
    "dhcpv6-server", "dns-dynamic", "dns-forwarding", "dummy", "ethernet",
    "event-handler", "extcommunity-list", "failover", "firewall/bridge",
    "firewall/flowtables", "firewall/global-options", "firewall/groups",
    "firewall/ipv4", "firewall/ipv6", "firewall/zones", "geneve",
    "high-availability", "https", "igmp-proxy", "input", "ipoe-server", "isis",
    "l2tpv3", "large-community-list", "lldp", "load-balancing", "local-route",
    "loopback", "macsec", "mpls", "nat", "nat64", "nat66", "ndp-proxy", "nhrp",
    "ntp", "openfabric", "openvpn", "ospf", "ospfv3", "pim", "pim6", "pki",
    "pppoe", "pppoe-server", "prefix-list", "pseudo-ethernet", "qos", "rip",
    "ripng", "route", "route-map", "router-advert", "rpki", "salt-minion",
    "service-monitoring", "sla", "snmp", "ssh", "sstpc", "static-routes",
    "system", "tftp-server", "traffic-engineering", "tunnel", "virtual-ethernet",
    "vpn/ipsec", "vpn/l2tp", "vpn/wireguard", "vpp", "vrf", "vti", "vxlan",
    "webproxy", "wireless", "wwan",
)

# Friendlier descriptions for common features; others fall back to a humanized slug.
_DESCRIPTIONS: dict[str, str] = {
    "nat": "Source/destination NAT rules",
    "nat64": "NAT64 (IPv6-to-IPv4) translation",
    "nat66": "NAT66 (IPv6-to-IPv6) translation",
    "dhcp": "DHCP server",
    "firewall/ipv4": "IPv4 firewall rules",
    "firewall/ipv6": "IPv6 firewall rules",
    "firewall/groups": "Firewall address/port/interface groups",
    "firewall/zones": "Firewall zones",
    "static-routes": "Static routes",
    "system": "System settings (hostname, DNS, NTP, etc.)",
    "vpn/ipsec": "IPsec VPN",
    "vpn/wireguard": "WireGuard VPN",
    "bgp": "BGP routing",
    "ospf": "OSPF routing",
    "qos": "Quality of Service / traffic shaping",
    "container": "Container applications",
}


def _humanize(slug: str) -> str:
    return slug.replace("/", " ").replace("-", " ").title()


@dataclass(frozen=True)
class Feature:
    slug: str
    description: str


FEATURES: tuple[Feature, ...] = tuple(
    Feature(slug, _DESCRIPTIONS.get(slug, _humanize(slug))) for slug in _SLUGS
)

_BY_SLUG: dict[str, Feature] = {f.slug: f for f in FEATURES}


def resolve_feature(feature: str) -> Feature:
    """Look up a feature by slug, raising a clear error for unknown values."""
    match = _BY_SLUG.get(feature.strip().lower())
    if match is None:
        raise ValueError(
            f"Unknown feature '{feature}'. Call list_features to see valid feature slugs."
        )
    return match
