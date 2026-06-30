"""Write tools — curated, typed configuration changes behind the propose/apply
guardrail. Registered only when VYMANAGER_ENABLE_WRITES is set.

Flow: a ``propose_*`` tool validates input and stores a Plan (touching nothing).
``apply_change`` executes a specific plan by id; ``confirm_change`` /
``discard_changes`` drive VyManager's commit-confirm and rollback.
"""

from __future__ import annotations

from typing import Any, Optional

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


async def _safe_get(path: str, instance_id: str) -> Optional[Any]:
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
        description: Optional[str] = None,
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
                "The change is LIVE but will AUTO-REVERT when the timer expires. Call "
                "confirm_change(instance_id) to keep it, or discard_changes(instance_id) "
                "to revert now."
            )
        else:
            response["commit_confirm"] = False
            response["next_step"] = (
                "The change is live immediately (no auto-rollback timer on this instance). "
                "Call discard_changes(instance_id) to revert unsaved changes if needed."
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
        """Discard all unsaved configuration changes on an instance (revert to last saved)."""
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
