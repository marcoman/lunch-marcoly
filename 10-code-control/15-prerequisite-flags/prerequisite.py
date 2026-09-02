"""Evaluate the parent and dependent flags for 15-prerequisite-flags.

LaunchDarkly: flag prerequisites and evaluation reasons.
https://launchdarkly.com/docs/home/flags/prereqs
Keywords: prerequisites, dependent flag, off variation
"""

from __future__ import annotations

from typing import Any

from ldclient import Context

# Dedicated keys — cite 11, do not share 11's inventory.
# LaunchDarkly: flag key=enable-grid-selection-highlight-prereq kind=string
# LaunchDarkly: flag key=show-navigation-move-count-prereq kind=boolean
FLAG_HIGHLIGHT = "enable-grid-selection-highlight-prereq"
FLAG_COUNT = "show-navigation-move-count-prereq"
VALID_COLORS = frozenset({"green", "yellow", "red", "blue", "purple", "pink"})


def normalize_username(username: str) -> str:
    """Return the normalized user context key used by both evaluations."""
    value = (username or "").strip().lower()
    if not value:
        raise ValueError("username is required")
    return value


def _reason_payload(reason: Any) -> dict[str, Any]:
    """Convert an SDK EvaluationReason into browser-friendly JSON."""
    if reason is None:
        return {"kind": "UNKNOWN"}
    if isinstance(reason, dict):
        return reason

    payload: dict[str, Any] = {"kind": getattr(reason, "kind", str(reason))}
    fields = {
        "rule_index": "ruleIndex",
        "rule_id": "ruleId",
        "prerequisite_key": "prerequisiteKey",
        "error_kind": "errorKind",
        "in_experiment": "inExperiment",
    }
    for attribute, json_key in fields.items():
        value = getattr(reason, attribute, None)
        if value is not None:
            payload[json_key] = value
    return payload


def _highlight_color(value: object) -> str:
    """Map the parent string variation to a supported UI color or none."""
    if not isinstance(value, str):
        return "none"
    candidate = value.strip().lower()
    return candidate if candidate in VALID_COLORS else "none"


def evaluate_prerequisite_flags(
    client: Any, username: str
) -> dict[str, Any]:
    """Evaluate parent and child independently; LaunchDarkly enforces dependency.

    The application deliberately calls variation_detail for the child even when
    the parent is off or non-green. A PREREQUISITE_FAILED reason proves the
    dependency came from flag configuration rather than application branching.
    """
    user_key = normalize_username(username)
    context = Context.builder(user_key).kind("user").build()

    if client is None:
        parent_detail = child_detail = None
        parent_value: object = "none"
        child_value = False
        parent_reason = child_reason = {"kind": "OFFLINE"}
    else:
        parent_detail = client.variation_detail(
            FLAG_HIGHLIGHT, context, "none"
        )
        child_detail = client.variation_detail(FLAG_COUNT, context, False)
        parent_value = parent_detail.value
        child_value = bool(child_detail.value)
        parent_reason = _reason_payload(parent_detail.reason)
        child_reason = _reason_payload(child_detail.reason)

    prerequisite_failed = child_reason.get("kind") == "PREREQUISITE_FAILED"
    # With this lab's configured off variation (`none`), green is the visible
    # evidence that the parent's required variation is being served. The child
    # reason independently proves whether LaunchDarkly rejected the dependency.
    prerequisite_met = (
        client is not None
        and parent_value == "green"
        and not prerequisite_failed
    )
    return {
        "username": user_key,
        "highlightColor": _highlight_color(parent_value),
        "showMoveCount": child_value,
        "prerequisiteMet": prerequisite_met,
        "ldContext": {"kind": "user", "key": user_key},
        "parent": {
            "key": FLAG_HIGHLIGHT,
            "value": parent_value,
            "variationIndex": (
                parent_detail.variation_index if parent_detail is not None else None
            ),
            "reason": parent_reason,
        },
        "child": {
            "key": FLAG_COUNT,
            "value": child_value,
            "variationIndex": (
                child_detail.variation_index if child_detail is not None else None
            ),
            "reason": child_reason,
        },
    }
