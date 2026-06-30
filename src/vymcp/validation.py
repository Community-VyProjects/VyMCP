"""Structural input validation for write proposers.

Deliberately thin: VyMCP does NOT reimplement VyOS's grammar (which values are
legal for which feature/version) — that is VyManager's and VyOS's job, surfaced
as an error at apply time. These checks only catch obviously malformed input
(empty, whitespace, oversized) so a plan carries clean tokens.
"""

from __future__ import annotations

MAX_VALUES = 50
MAX_NAME_LEN = 100


def validate_identifier(value: str, what: str = "name") -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{what} must not be empty.")
    if any(c.isspace() for c in cleaned):
        raise ValueError(f"{what} must not contain whitespace.")
    if len(cleaned) > MAX_NAME_LEN:
        raise ValueError(f"{what} is too long (max {MAX_NAME_LEN} characters).")
    return cleaned


def validate_values(values: list[str], what: str = "value") -> list[str]:
    if not values:
        raise ValueError(f"Provide at least one {what}.")
    if len(values) > MAX_VALUES:
        raise ValueError(f"Too many {what}s ({len(values)}); max {MAX_VALUES} per call.")
    cleaned = []
    for value in values:
        token = value.strip()
        if not token:
            raise ValueError(f"{what} must not be empty.")
        if any(c.isspace() for c in token):
            raise ValueError(f"{what} '{value}' must not contain whitespace.")
        cleaned.append(token)
    return cleaned
