import httpx
import pytest


def _apply_handler(batch_response, cc_active=True, seconds=55):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/vyos/config/diff":
            return httpx.Response(200, json={"has_changes": True, "summary": {"added": 1}})
        if path == "/vyos/config/commit-confirm/status":
            return httpx.Response(200, json={"active": cc_active, "seconds_remaining": seconds})
        if path.endswith("/batch"):
            return httpx.Response(200, json=batch_response)
        return httpx.Response(404, json={})
    return handler


# ---- kill-switch -----------------------------------------------------------

def test_killswitch_off_registers_nothing(monkeypatch, collect_write_tools):
    monkeypatch.delenv("VYMANAGER_ENABLE_WRITES", raising=False)
    assert collect_write_tools() == {}


def test_killswitch_on_registers_tools(write_tools):
    assert "apply_change" in write_tools
    assert "propose_create_address_group" in write_tools


# ---- propose touches nothing ----------------------------------------------

def test_propose_does_not_call_vymanager(write_tools, install_client):
    def explode(request):
        raise AssertionError("propose must not make HTTP calls")
    install_client(explode)
    result = write_tools["propose_create_address_group"]("i1", "WEB", ["10.0.0.1"])
    assert result["applied"] is False
    assert result["plan_id"].startswith("plan_")


# ---- apply guardrails ------------------------------------------------------

async def test_apply_requires_confirm(write_tools):
    plan = write_tools["propose_create_address_group"]("i1", "WEB", ["10.0.0.1"])
    with pytest.raises(ValueError, match="confirm"):
        await write_tools["apply_change"](plan["plan_id"], confirm=False)


async def test_apply_unknown_plan(write_tools):
    with pytest.raises(ValueError, match="expired|Unknown"):
        await write_tools["apply_change"]("plan_does_not_exist", confirm=True)


async def test_apply_success_and_single_use(write_tools, install_client):
    install_client(_apply_handler({"success": True}))
    plan = write_tools["propose_create_address_group"]("i1", "WEB", ["10.0.0.1"])
    res = await write_tools["apply_change"](plan["plan_id"], confirm=True)
    assert res["applied"] is True
    assert res["commit_confirm"] is True
    assert res["seconds_remaining"] == 55
    # plan is consumed -> replay refused
    with pytest.raises(ValueError):
        await write_tools["apply_change"](plan["plan_id"], confirm=True)


async def test_apply_logical_failure_not_applied(write_tools, install_client):
    install_client(_apply_handler({"success": False, "error": "rejected by VyOS"}))
    plan = write_tools["propose_create_address_group"]("i1", "WEB", ["10.0.0.1"])
    res = await write_tools["apply_change"](plan["plan_id"], confirm=True)
    assert res["applied"] is False
    assert "rejected" in res["error"]
    # a failed apply leaves the plan usable for a retry
    from vymcp.changes import plan_store
    assert plan_store.get(plan["plan_id"]) is not None


async def test_apply_read_only_token_blocked(write_tools, install_client):
    def handler(request):
        if request.url.path == "/vyos/config/diff":
            return httpx.Response(200, json={})
        return httpx.Response(403, json={"detail": "This API token is read-only."})
    install_client(handler)
    plan = write_tools["propose_create_address_group"]("i1", "WEB", ["10.0.0.1"])
    from vymcp.client import VyManagerError
    with pytest.raises(VyManagerError, match="read-only"):
        await write_tools["apply_change"](plan["plan_id"], confirm=True)


async def test_apply_no_commit_confirm(write_tools, install_client):
    install_client(_apply_handler({"success": True}, cc_active=False))
    plan = write_tools["propose_create_address_group"]("i1", "WEB", ["10.0.0.1"])
    res = await write_tools["apply_change"](plan["plan_id"], confirm=True)
    assert res["applied"] is True
    assert res["commit_confirm"] is False
    assert "inverse change" in res["next_step"]


async def test_discard_refused_during_commit_confirm(write_tools, install_client):
    def handler(request):
        if request.url.path == "/vyos/config/commit-confirm/status":
            return httpx.Response(200, json={"active": True, "seconds_remaining": 30})
        return httpx.Response(200, json={"success": True})
    install_client(handler)
    with pytest.raises(ValueError, match="commit-confirm is active"):
        await write_tools["discard_changes"]("i1")


async def test_discard_ok_when_no_commit_confirm(write_tools, install_client):
    def handler(request):
        if request.url.path == "/vyos/config/commit-confirm/status":
            return httpx.Response(200, json={"active": False})
        if request.url.path == "/vyos/config/discard":
            return httpx.Response(200, json={"success": True, "message": "discarded"})
        return httpx.Response(404, json={})
    install_client(handler)
    res = await write_tools["discard_changes"]("i1")
    assert res["discarded"] is True
