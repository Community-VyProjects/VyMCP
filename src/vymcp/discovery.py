"""Feature write-vocabulary discovery.

Combines two machine-readable sources from VyManager so VyMCP never hard-codes a
feature's operations:

- ``GET /vyos/operations/<feature>`` — the op vocabulary (names, arg counts,
  descriptions), introspected from the feature's batch builder.
- ``GET /openapi.json`` — the batch endpoint's top-level body fields (e.g.
  ``nat_type``, ``group_name``) and which are required.

Both are static per VyManager deployment, so results are cached.
"""

from __future__ import annotations

from typing import Any

from .client import current_client

_feature_cache: dict[str, dict[str, Any]] = {}
_openapi_spec: dict[str, Any] | None = None


def clear_cache() -> None:
    """Drop cached discovery data (used by tests and on reconnect)."""
    global _openapi_spec
    _feature_cache.clear()
    _openapi_spec = None


async def _get_feature(feature: str) -> dict[str, Any]:
    if feature not in _feature_cache:
        _feature_cache[feature] = await current_client().get(f"/vyos/operations/{feature}")
    return _feature_cache[feature]


async def get_feature_operations(feature: str) -> list[dict[str, Any]]:
    """Op vocabulary for a feature. Raises VyManagerError if the feature is unknown."""
    return (await _get_feature(feature)).get("operations", [])


async def get_subject_field(feature: str) -> str | None:
    """The top-level field injected as each op's first arg, or None for plain features."""
    return (await _get_feature(feature)).get("subject_field")


def _resolve_ref(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not ref:
        return schema
    node: Any = spec
    for part in ref.lstrip("#/").split("/"):
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


async def get_top_level_fields(feature: str) -> dict[str, dict[str, Any]]:
    """Top-level batch-body fields (besides ``operations``) for a feature.

    Best-effort: returns {} if the spec can't be read or the feature has none.
    """
    global _openapi_spec
    if _openapi_spec is None:
        try:
            _openapi_spec = await current_client().get("/openapi.json")
        except Exception:
            return {}

    post = _openapi_spec.get("paths", {}).get(f"/vyos/{feature}/batch", {}).get("post")
    if not post:
        return {}
    schema_ref = (
        post.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    schema = _resolve_ref(_openapi_spec, schema_ref)
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    fields: dict[str, dict[str, Any]] = {}
    for name, prop in properties.items():
        if name == "operations":
            continue
        fields[name] = {"required": name in required, "type": prop.get("type")}
    return fields
