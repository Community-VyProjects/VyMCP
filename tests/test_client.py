import httpx
import pytest
from tests.conftest import make_client

from vymcp.client import VyManagerError


def _client_returning(status, json=None, raise_exc=None):
    def handler(request):
        if raise_exc:
            raise raise_exc
        return httpx.Response(status, json=json if json is not None else {})
    return make_client(handler)


async def test_get_happy_path():
    c = _client_returning(200, json={"ok": True})
    assert await c.get("/x") == {"ok": True}


async def test_post_sends_json_and_header():
    seen = {}

    def handler(request):
        seen["instance"] = request.headers.get("X-VyOS-Instance-Id")
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"success": True})

    c = make_client(handler)
    await c.post("/vyos/x/batch", instance_id="inst1", json={"a": 1})
    assert seen["instance"] == "inst1"
    assert seen["auth"] == "Bearer vym_test"


async def test_401_message():
    c = _client_returning(401, json={"detail": "no"})
    with pytest.raises(VyManagerError, match="token"):
        await c.get("/x")


async def test_403_includes_detail():
    c = _client_returning(403, json={"detail": "This API token is read-only."})
    with pytest.raises(VyManagerError, match="read-only"):
        await c.get("/x", instance_id="i")


async def test_404_without_instance_hints_instance():
    c = _client_returning(404, json={})
    with pytest.raises(VyManagerError, match="instance_id"):
        await c.get("/x")


async def test_404_with_instance():
    c = _client_returning(404, json={})
    with pytest.raises(VyManagerError, match="scoped|exist"):
        await c.get("/x", instance_id="i")


async def test_request_error_wrapped():
    c = _client_returning(0, raise_exc=httpx.ConnectError("boom"))
    with pytest.raises(VyManagerError, match="Could not reach"):
        await c.get("/x")
