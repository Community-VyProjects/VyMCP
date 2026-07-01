"""Write tools — curated, typed configuration changes behind the propose/apply
guardrail. Registered only when VYMANAGER_ENABLE_WRITES is set.

Flow: a ``propose_*`` tool validates input and stores a Plan (touching nothing).
``apply_change`` executes a specific plan by id; ``confirm_change`` /
``discard_changes`` drive VyManager's commit-confirm and rollback.
"""

from __future__ import annotations

from typing import Any

from . import discovery
from .changes import Plan, plan_store
from .client import VyManagerError, get_client
from .config import writes_enabled
from .validation import validate_identifier, validate_values

FIREWALL_GROUPS_PATH = "/vyos/firewall/groups/batch"

_CONFIG_DIFF = "/vyos/config/diff"
_CC_STATUS = "/vyos/config/commit-confirm/status"
_CC_CONFIRM = "/vyos/config/commit-confirm/confirm"
_DISCARD = "/vyos/config/discard"


def _plan_response(plan: Plan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "instance_id": plan.instance_id,
        "summary": plan.summary,
        "operations": plan.operations,
        "applied": False,
        "next_step": (
            "Show this plan to the user. To apply it after their approval, call "
            "apply_change(plan_id, confirm=true). Nothing has changed yet."
        ),
    }


async def _safe_get(path: str, instance_id: str) -> Any | None:
    """Best-effort read used to enrich an apply response; never fails the apply."""
    try:
        return await get_client().get(path, instance_id=instance_id)
    except VyManagerError:
        return None


def register_write_tools(mcp) -> None:
    # Operator kill-switch: in a read-only deployment, no change tools exist at all.
    if not writes_enabled():
        return

    # ---- Proposers (no device interaction) --------------------------------

    @mcp.tool()
    def propose_create_address_group(
        instance_id: str,
        name: str,
        addresses: list[str],
        description: str | None = None,
    ) -> dict[str, Any]:
        """Propose creating an IPv4 firewall address-group. Does NOT apply.

        Returns a plan_id to pass to apply_change after the user approves.

        Args:
            instance_id: Target instance (from list_instances).
            name: Group name.
            addresses: Host IPs or 'start-end' ranges, 1-50 (a VyOS address-group
                does not accept CIDR networks — those belong in a network-group).
            description: Optional description.
        """
        gname = validate_identifier(name, "group name")
        members = validate_values(addresses, "address")
        ops: list[dict[str, Any]] = [{"op": "set_address_group"}]
        if description:
            ops.append({"op": "set_address_group_description", "value": description})
        ops += [{"op": "set_address_group_address", "value": m} for m in members]
        summary = (
            f"Create IPv4 address-group '{gname}' on {instance_id} with "
            f"{len(members)} member(s): {', '.join(members)}"
            + (f"; description {description!r}" if description else "")
        )
        plan = plan_store.create(
            instance_id=instance_id,
            feature="firewall/groups",
            path=FIREWALL_GROUPS_PATH,
            body={"group_name": gname, "operations": ops},
            summary=summary,
            operations=ops,
        )
        return _plan_response(plan)

    @mcp.tool()
    def propose_add_address_group_members(
        instance_id: str, name: str, addresses: list[str]
    ) -> dict[str, Any]:
        """Propose adding members to an existing IPv4 firewall address-group. Does NOT apply."""
        gname = validate_identifier(name, "group name")
        members = validate_values(addresses, "address")
        ops = [{"op": "set_address_group_address", "value": m} for m in members]
        summary = (
            f"Add {len(members)} member(s) to address-group '{gname}' on "
            f"{instance_id}: {', '.join(members)}"
        )
        plan = plan_store.create(
            instance_id=instance_id,
            feature="firewall/groups",
            path=FIREWALL_GROUPS_PATH,
            body={"group_name": gname, "operations": ops},
            summary=summary,
            operations=ops,
        )
        return _plan_response(plan)

    @mcp.tool()
    def propose_remove_address_group_members(
        instance_id: str, name: str, addresses: list[str]
    ) -> dict[str, Any]:
        """Propose removing members from an IPv4 firewall address-group. Does NOT apply."""
        gname = validate_identifier(name, "group name")
        members = validate_values(addresses, "address")
        ops = [{"op": "delete_address_group_address", "value": m} for m in members]
        summary = (
            f"Remove {len(members)} member(s) from address-group '{gname}' on "
            f"{instance_id}: {', '.join(members)}"
        )
        plan = plan_store.create(
            instance_id=instance_id,
            feature="firewall/groups",
            path=FIREWALL_GROUPS_PATH,
            body={"group_name": gname, "operations": ops},
            summary=summary,
            operations=ops,
        )
        return _plan_response(plan)

    @mcp.tool()
    def propose_delete_address_group(instance_id: str, name: str) -> dict[str, Any]:
        """Propose deleting an entire IPv4 firewall address-group. Does NOT apply.

        Deleting a group in use by firewall rules can break those rules — review carefully.
        """
        gname = validate_identifier(name, "group name")
        ops = [{"op": "delete_address_group"}]
        summary = (
            f"DELETE the entire IPv4 address-group '{gname}' on {instance_id}. "
            "Any firewall rule referencing it may be affected."
        )
        plan = plan_store.create(
            instance_id=instance_id,
            feature="firewall/groups",
            path=FIREWALL_GROUPS_PATH,
            body={"group_name": gname, "operations": ops},
            summary=summary,
            operations=ops,
        )
        return _plan_response(plan)

    # ---- Generic, discovery-driven proposing -------------------------------

    @mcp.tool()
    async def describe_feature_operations(feature: str) -> dict[str, Any]:
        """List the operations available for a feature, for use with propose_operations.

        Returns each op's name, arg_count, and description, plus any required
        top-level body fields (e.g. nat_type, group_name).

        Args:
            feature: A feature slug from list_features (e.g. "nat", "static-routes").
        """
        operations = await discovery.get_feature_operations(feature)
        fields = await discovery.get_top_level_fields(feature)
        subject_field = await discovery.get_subject_field(feature)
        return {
            "feature": feature,
            "subject_field": subject_field,
            "top_level_fields": fields,
            "operations": operations,
            "note": (
                f"This feature requires the '{subject_field}' field (the subject, e.g. the "
                f"interface name); each op's value supplies the args after it."
                if subject_field
                else None
            ),
        }

    @mcp.tool()
    async def propose_operations(
        feature: str,
        instance_id: str,
        operations: list[dict[str, Any]],
        fields: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Propose a batch of operations for any feature. Does NOT apply.

        Each operation is ``{"op": <name>, "value": <str>}`` where op comes from
        describe_feature_operations. Two-argument ops take a comma-joined value.
        Returns a plan_id to pass to apply_change after the user approves.

        Args:
            feature: A feature slug (e.g. "nat", "static-routes").
            instance_id: Target instance from list_instances.
            operations: The operations to perform.
            fields: Required top-level body fields for the feature, if any
                (see describe_feature_operations).
        """
        vocab = {o["op"]: o for o in await discovery.get_feature_operations(feature)}
        if not operations:
            raise ValueError("Provide at least one operation.")

        # Subject features inject a top-level field as each op's first arg, so the
        # op value only supplies the args AFTER it.
        subject_field = await discovery.get_subject_field(feature)
        if subject_field and not (fields or {}).get(subject_field):
            raise ValueError(
                f"'{feature}' requires the '{subject_field}' field (e.g. the interface "
                f"name); pass it in fields."
            )
        subject_args = 1 if subject_field else 0

        normalized: list[dict[str, Any]] = []
        for op in operations:
            name = op.get("op")
            if name not in vocab:
                raise ValueError(
                    f"Unknown operation '{name}' for '{feature}'. Call "
                    f"describe_feature_operations('{feature}') for the vocabulary."
                )
            value = op.get("value")
            if vocab[name]["arg_count"] - subject_args >= 1 and not value:
                raise ValueError(f"Operation '{name}' requires a value.")
            entry: dict[str, Any] = {"op": name}
            if value is not None:
                entry["value"] = value
            normalized.append(entry)

        body: dict[str, Any] = dict(fields or {})
        body["operations"] = normalized
        summary = (
            f"{len(normalized)} operation(s) on '{feature}' (instance {instance_id})"
            + (f"; fields {fields}" if fields else "")
        )
        plan = plan_store.create(
            instance_id=instance_id,
            feature=feature,
            path=f"/vyos/{feature}/batch",
            body=body,
            summary=summary,
            operations=normalized,
        )
        return _plan_response(plan)

    # ---- Change management -------------------------------------------------

    @mcp.tool()
    async def apply_change(plan_id: str, confirm: bool = False) -> dict[str, Any]:
        """Apply a previously proposed plan to the router.

        Requires confirm=true and a valid, unexpired plan_id from a propose tool.
        The change is applied with VyManager's commit-confirm auto-rollback when the
        instance supports it; this tool never confirms for you.

        Args:
            plan_id: The id returned by a propose tool.
            confirm: Must be true to proceed (set only after the user approves).
        """
        if not confirm:
            raise ValueError(
                "Refusing to apply: set confirm=true only after the user has reviewed "
                "and approved this exact plan."
            )
        plan = plan_store.get(plan_id)
        if plan is None:
            raise ValueError(
                "Unknown or expired plan_id. Re-run the propose tool, show the user the "
                "new plan, then apply it."
            )

        client = get_client()

        # Prime VyManager's diff baseline before changing anything. Its snapshot is
        # initialized on first read, so without this the post-change diff/discard
        # would be measured against the already-changed config.
        await _safe_get(_CONFIG_DIFF, plan.instance_id)

        result = await client.post(plan.path, instance_id=plan.instance_id, json=plan.body)

        # Feature batch endpoints return {success, error} with HTTP 200 even on a
        # logical failure (e.g. a rejected commit), so check the body.
        if isinstance(result, dict) and result.get("success") is False:
            return {
                "applied": False,
                "plan_id": plan_id,
                "error": result.get("error") or "VyManager reported the change failed.",
                "note": (
                    "VyManager/VyOS rejected the change; nothing was applied. Check that "
                    "the values are valid for this feature on this VyOS version, then "
                    "propose again."
                ),
            }

        plan_store.consume(plan_id)

        status = await _safe_get(_CC_STATUS, plan.instance_id)
        diff = await _safe_get(_CONFIG_DIFF, plan.instance_id)

        response: dict[str, Any] = {
            "applied": True,
            "summary": plan.summary,
            "changed": diff.get("summary") if isinstance(diff, dict) else None,
        }
        if isinstance(status, dict) and status.get("active"):
            response["commit_confirm"] = True
            response["seconds_remaining"] = status.get("seconds_remaining")
            response["next_step"] = (
                "The change is LIVE, protected by commit-confirm: if it cut off access to "
                "the router, the device auto-reverts (reboots) when the timer expires and "
                "you regain access — so do nothing in that case. If access is fine, call "
                "confirm_change(instance_id) to keep it. To UNDO a change that did not lock "
                "you out, confirm_change first, then apply the inverse change (e.g. the "
                "matching delete ops)."
            )
        else:
            response["commit_confirm"] = False
            response["next_step"] = (
                "The change is live immediately (no commit-confirm safety net on this "
                "instance). To undo it, apply the inverse change (the matching delete ops)."
            )
        return response

    @mcp.tool()
    async def confirm_change(instance_id: str) -> dict[str, Any]:
        """Confirm an active commit-confirm, making the change permanent and saving it."""
        result = await get_client().post(_CC_CONFIRM, instance_id=instance_id)
        return {
            "confirmed": bool(result.get("success", True)) if isinstance(result, dict) else True,
            "message": result.get("message") if isinstance(result, dict) else None,
            "error": result.get("error") if isinstance(result, dict) else None,
        }

    @mcp.tool()
    async def discard_changes(instance_id: str) -> dict[str, Any]:
        """Discard unsaved configuration changes on an instance (revert to last saved).

        Only valid when NO commit-confirm is pending. While a commit-confirm is
        active the device is in a pending-reboot state, so to undo such a change
        confirm_change first and then apply the inverse change instead.
        """
        status = await _safe_get(_CC_STATUS, instance_id)
        if isinstance(status, dict) and status.get("active"):
            raise ValueError(
                "A commit-confirm is active for this instance, so discard is unsafe. "
                "If the change locked you out, wait for the auto-revert. Otherwise call "
                "confirm_change(instance_id), then apply the inverse change to undo it."
            )
        result = await get_client().post(_DISCARD, instance_id=instance_id)
        return {
            "discarded": bool(result.get("success", True)) if isinstance(result, dict) else True,
            "message": result.get("message") if isinstance(result, dict) else None,
            "error": result.get("error") if isinstance(result, dict) else None,
        }

    @mcp.tool()
    async def get_pending_changes(instance_id: str) -> dict[str, Any]:
        """Show unsaved changes and any active commit-confirm rollback timer for an instance."""
        client = get_client()
        diff = await client.get(_CONFIG_DIFF, instance_id=instance_id)
        status = await client.get(_CC_STATUS, instance_id=instance_id)
        return {
            "has_changes": diff.get("has_changes") if isinstance(diff, dict) else None,
            "summary": diff.get("summary") if isinstance(diff, dict) else None,
            "commit_confirm": status,
        }
