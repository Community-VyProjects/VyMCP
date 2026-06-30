import httpx
import pytest

from vymcp import server


def _router(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/session/sites":
        return httpx.Response(200, json=[{"id": "s1", "name": "HQ"}])
    if path == "/session/sites/s1/instances":
        return httpx.Response(200, json=[{
            "id": "i1", "name": "edge", "host": "10.0.0.1",
            "vyos_version": "1.5", "is_active": True,
        }])
    if path == "/vyos/nat/capabilities":
        return httpx.Response(200, json={"version": "1.5", "features": {}})
    if path == "/vyos/nat/config":
        return httpx.Response(200, json={"source": []})
    return httpx.Response(404, json={})


async def test_list_instances_flattens(install_client):
    install_client(_router)
    out = await server.list_instances()
    assert out == [{
        "instance_id": "i1", "name": "edge", "site": "HQ",
        "host": "10.0.0.1", "vyos_version": "1.5", "is_active": True,
    }]


def test_list_features_returns_registry():
    out = server.list_features()
    assert {"feature", "description"} <= set(out[0])
    assert any(f["feature"] == "nat" for f in out)


async def test_get_capabilities(install_client):
    install_client(_router)
    caps = await server.get_capabilities("nat", "i1")
    assert caps["version"] == "1.5"


async def test_get_config_resolves_feature(install_client):
    install_client(_router)
    cfg = await server.get_config("NAT", "i1")  # case-insensitive
    assert cfg == {"source": []}


async def test_get_config_unknown_feature(install_client):
    install_client(_router)
    with pytest.raises(ValueError):
        await server.get_config("bogus", "i1")
