"""Change-management plan store — the core write guardrail.

A *plan* is a fully-formed, validated configuration change that has not been
applied. Proposers create plans (touching nothing); ``apply_change`` executes a
plan by id. Plans are:

- **single-use** — consumed on successful apply, so they cannot be replayed;
- **TTL-bound** — a stale plan cannot be applied;
- **instance-bound** — a plan carries its target instance and cannot be redirected.

In-memory by design (one stdio process). A hosted, multi-worker deployment would
need shared storage — tracked as hardening.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any

DEFAULT_TTL_SECONDS = 600  # 10 minutes


@dataclass
class Plan:
    plan_id: str
    owner: str  # the caller who proposed it; only they may apply it
    instance_id: str
    feature: str
    path: str  # VyManager endpoint the apply will POST to
    body: dict[str, Any]  # exact request body
    summary: str  # human-readable description of the change
    operations: list[dict[str, Any]]  # for display/review
    created_at: float = field(default_factory=time.monotonic)

    def age_seconds(self) -> float:
        return time.monotonic() - self.created_at


class PlanStore:
    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._plans: dict[str, Plan] = {}

    def _prune(self) -> None:
        expired = [pid for pid, p in self._plans.items() if p.age_seconds() > self._ttl]
        for pid in expired:
            del self._plans[pid]

    def create(
        self,
        *,
        owner: str,
        instance_id: str,
        feature: str,
        path: str,
        body: dict[str, Any],
        summary: str,
        operations: list[dict[str, Any]],
    ) -> Plan:
        self._prune()
        plan = Plan(
            plan_id="plan_" + secrets.token_hex(8),
            owner=owner,
            instance_id=instance_id,
            feature=feature,
            path=path,
            body=body,
            summary=summary,
            operations=operations,
        )
        self._plans[plan.plan_id] = plan
        return plan

    def get(self, plan_id: str, owner: str) -> Plan | None:
        """Return the plan only if it exists and belongs to ``owner``."""
        self._prune()
        plan = self._plans.get(plan_id)
        if plan is None or plan.owner != owner:
            return None
        return plan

    def consume(self, plan_id: str) -> None:
        """Remove a plan after it has been successfully applied (single-use)."""
        self._plans.pop(plan_id, None)


# Process-wide store shared by the proposer and apply tools.
plan_store = PlanStore()
