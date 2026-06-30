import time

from vymcp.changes import PlanStore


def _make(store, instance_id="inst1"):
    return store.create(
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
    assert store.get(plan.plan_id) is plan
    assert plan.instance_id == "inst1"


def test_consume_is_single_use():
    store = PlanStore()
    plan = _make(store)
    store.consume(plan.plan_id)
    assert store.get(plan.plan_id) is None
    # consuming again is a no-op, not an error
    store.consume(plan.plan_id)


def test_expired_plan_is_pruned():
    store = PlanStore(ttl_seconds=60)
    plan = _make(store)
    # Backdate creation beyond the TTL.
    store._plans[plan.plan_id].created_at = time.monotonic() - 600
    assert store.get(plan.plan_id) is None


def test_unique_ids():
    store = PlanStore()
    ids = {_make(store).plan_id for _ in range(50)}
    assert len(ids) == 50
