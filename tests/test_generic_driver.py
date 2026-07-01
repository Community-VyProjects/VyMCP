import httpx
import pytest

_VOCAB = {
    "feature": "nat",
    "operations": [
        {"op": "set_source_rule", "args": ["rule"], "arg_count": 1, "description": "Rule."},
        {"op": "set_source_rule_translation_address", "args": ["rule", "addr"],
         "arg_count": 2, "description": "Translation address."},
        {"op": "delete_all", "args": [], "arg_count": 0, "description": "Delete all."},
    ],
}

_OPENAPI = {
    "paths": {
        "/vyos/nat/batch": {
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/NATBatchRequest"}
                        }
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "NATBatchRequest": {
                "properties": {
                    "nat_type": {"type": "string"},
                    "operations": {"type": "array"},
                },
                "required": ["nat_type", "operations"],
            }
        }
    },
}


def _discovery_handler(extra=None):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/vyos/operations/nat":
            return httpx.Response(200, json=_VOCAB)
        if path == "/openapi.json":
            return httpx.Response(200, json=_OPENAPI)
        if extra:
            r = extra(request)
            if r is not None:
                return r
        return httpx.Response(404, json={})
    return handler


async def test_describe_merges_ops_and_fields(write_tools, install_client):
    install_client(_discovery_handler())
    out = await write_tools["describe_feature_operations"]("nat")
    assert {o["op"] for o in out["operations"]} == {
        "set_source_rule", "set_source_rule_translation_address", "delete_all"
    }
    assert out["top_level_fields"]["nat_type"]["required"] is True


async def test_propose_builds_body_with_fields(write_tools, install_client):
    install_client(_discovery_handler())
    plan = await write_tools["propose_operations"](
        "nat", "i1",
        [{"op": "set_source_rule", "value": "100"}],
        fields={"nat_type": "source"},
    )
    assert plan["applied"] is False
    from vymcp.changes import plan_store
    body = plan_store.get(plan["plan_id"], "local").body
    assert body == {"nat_type": "source", "operations": [{"op": "set_source_rule", "value": "100"}]}


async def test_propose_rejects_unknown_op(write_tools, install_client):
    install_client(_discovery_handler())
    with pytest.raises(ValueError, match="Unknown operation"):
        await write_tools["propose_operations"]("nat", "i1", [{"op": "set_bogus", "value": "x"}])


async def test_propose_requires_value_for_arg_op(write_tools, install_client):
    install_client(_discovery_handler())
    with pytest.raises(ValueError, match="requires a value"):
        await write_tools["propose_operations"]("nat", "i1", [{"op": "set_source_rule"}])


async def test_propose_zero_arg_op_needs_no_value(write_tools, install_client):
    install_client(_discovery_handler())
    plan = await write_tools["propose_operations"]("nat", "i1", [{"op": "delete_all"}])
    from vymcp.changes import plan_store
    assert plan_store.get(plan["plan_id"], "local").body["operations"] == [{"op": "delete_all"}]


async def test_propose_rejects_empty(write_tools, install_client):
    install_client(_discovery_handler())
    with pytest.raises(ValueError, match="at least one"):
        await write_tools["propose_operations"]("nat", "i1", [])


_BONDING = {
    "feature": "bonding",
    "subject_field": "interface_name",
    "operations": [
        {"op": "set_interface_disable", "args": ["interface"], "arg_count": 1, "description": "x"},
        {"op": "set_interface_address", "args": ["interface", "addr"],
         "arg_count": 2, "description": "x"},
    ],
}


def _bonding_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/vyos/operations/bonding":
        return httpx.Response(200, json=_BONDING)
    if request.url.path == "/openapi.json":
        return httpx.Response(200, json={"paths": {}})
    return httpx.Response(404, json={})


async def test_subject_feature_requires_subject(write_tools, install_client):
    install_client(_bonding_handler)
    with pytest.raises(ValueError, match="interface_name"):
        await write_tools["propose_operations"](
            "bonding", "i1", [{"op": "set_interface_disable"}]
        )


async def test_subject_feature_zero_value_op_ok(write_tools, install_client):
    install_client(_bonding_handler)
    # set_interface_disable has arg_count 1, but the subject consumes it -> no value needed
    plan = await write_tools["propose_operations"](
        "bonding", "i1", [{"op": "set_interface_disable"}], fields={"interface_name": "bond0"}
    )
    from vymcp.changes import plan_store
    body = plan_store.get(plan["plan_id"], "local").body
    assert body == {"interface_name": "bond0", "operations": [{"op": "set_interface_disable"}]}


async def test_subject_feature_value_op_needs_value(write_tools, install_client):
    install_client(_bonding_handler)
    # set_interface_address has arg_count 2; minus the subject -> 1 value arg required
    with pytest.raises(ValueError, match="requires a value"):
        await write_tools["propose_operations"](
            "bonding", "i1", [{"op": "set_interface_address"}], fields={"interface_name": "bond0"}
        )


async def test_generic_plan_applies(write_tools, install_client):
    def extra(request):
        p = request.url.path
        if p == "/vyos/config/diff":
            return httpx.Response(200, json={"summary": {"added": 1}})
        if p == "/vyos/config/commit-confirm/status":
            return httpx.Response(200, json={"active": True, "seconds_remaining": 50})
        if p == "/vyos/nat/batch":
            return httpx.Response(200, json={"success": True})
        return None

    install_client(_discovery_handler(extra))
    plan = await write_tools["propose_operations"](
        "nat", "i1", [{"op": "set_source_rule", "value": "100"}], fields={"nat_type": "source"}
    )
    res = await write_tools["apply_change"](plan["plan_id"], confirm=True)
    assert res["applied"] is True
    assert res["commit_confirm"] is True
