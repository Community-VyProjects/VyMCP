import httpx
import pytest

from vymcp.client import VyManagerError


def _resp(status, json=None, raise_exc=None):
    def handler(request):
        if raise_exc:
            raise raise_exc
        return httpx.Response(status, json=json if json is not None else {})
    return handler


async def test_get_happy_path(make_mock_client):
    c = make_mock_client(_resp(200, json={"ok": True}))
    assert await c.get("/x") == {"ok": True}


async def test_post_sends_json_and_header(make_mock_client):
    seen = {}

    def handler(request):
        seen["instance"] = request.headers.get("X-VyOS-Instance-Id")
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"success": True})

    await make_mock_client(handler).post("/vyos/x/batch", instance_id="inst1", json={"a": 1})
    assert seen["instance"] == "inst1"
    assert seen["auth"] == "Bearer vym_test"


async def test_401_message(make_mock_client):
    with pytest.raises(VyManagerError, match="token"):
        await make_mock_client(_resp(401, json={"detail": "no"})).get("/x")


async def test_403_includes_detail(make_mock_client):
    c = make_mock_client(_resp(403, json={"detail": "This API token is read-only."}))
    with pytest.raises(VyManagerError, match="read-only"):
        await c.get("/x", instance_id="i")


async def test_404_without_instance_hints_instance(make_mock_client):
    with pytest.raises(VyManagerError, match="instance_id"):
        await make_mock_client(_resp(404, json={})).get("/x")


async def test_404_with_instance(make_mock_client):
    with pytest.raises(VyManagerError, match="scoped|exist"):
        await make_mock_client(_resp(404, json={})).get("/x", instance_id="i")


async def test_request_error_wrapped(make_mock_client):
    c = make_mock_client(_resp(0, raise_exc=httpx.ConnectError("boom")))
    with pytest.raises(VyManagerError, match="Could not reach"):
        await c.get("/x")
