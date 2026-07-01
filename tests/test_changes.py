import time

from vymcp.changes import PlanStore


def _make(store, owner="u1", instance_id="inst1"):
    return store.create(
        owner=owner,
        instance_id=instance_id,
        feature="firewall/groups",
        path="/vyos/firewall/groups/batch",
        body={"group_name": "G", "operations": []},
        summary="test",
        operations=[],
    )


def test_create_and_get():
    store = PlanStore()
    plan = _make(store)
    assert plan.plan_id.startswith("plan_")
    assert store.get(plan.plan_id, "u1") is plan
    assert plan.instance_id == "inst1"


def test_get_enforces_owner():
    store = PlanStore()
    plan = _make(store, owner="alice")
    assert store.get(plan.plan_id, "bob") is None  # not yours
    assert store.get(plan.plan_id, "alice") is plan


def test_consume_is_single_use():
    store = PlanStore()
    plan = _make(store)
    store.consume(plan.plan_id)
    assert store.get(plan.plan_id, "u1") is None
    store.consume(plan.plan_id)  # no-op, not an error


def test_expired_plan_is_pruned():
    store = PlanStore(ttl_seconds=60)
    plan = _make(store)
    store._plans[plan.plan_id].created_at = time.monotonic() - 600
    assert store.get(plan.plan_id, "u1") is None


def test_unique_ids():
    store = PlanStore()
    ids = {_make(store).plan_id for _ in range(50)}
    assert len(ids) == 50
