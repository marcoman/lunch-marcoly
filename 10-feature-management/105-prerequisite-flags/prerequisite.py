"""Evaluate the parent and two dependent flags for 105-prerequisite-flags.

LaunchDarkly: flag prerequisites and evaluation reasons.
https://launchdarkly.com/docs/home/flags/prereqs
Keywords: prerequisites, dependent flag, off variation
"""

from __future__ import annotations

import platform
from typing import Any

from ldclient import Context

# Feature flags — prerequisites. Both children evaluate only when the parent is green.
# https://launchdarkly.com/docs/home/flags/prereqs
FLAG_HIGHLIGHT = "enable-grid-selection-highlight-prereq"
FLAG_COUNT = "show-navigation-move-count-prereq"
FLAG_EMOJI = "show-anonymous-host-os-emoji-prereq"
VALID_COLORS = frozenset({"green", "yellow", "red", "blue", "purple", "pink"})
# Display only. Cites 102's host emoji. This lab does not build an anonymous context.
OS_EMOJI = {"linux": "🐧", "macos": "🍎", "windows": "🪟", "other": "😊"}


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


def detect_host_os() -> str:
    """Map the machine OS to the emoji key. Not a LaunchDarkly context attribute."""
    system = platform.system().lower()
    if system == "linux":
        return "linux"
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    return "other"


def host_emoji(show: bool, host_os: str) -> str:
    """Return the host emoji when the emoji child evaluates true."""
    if not show:
        return ""
    return OS_EMOJI.get(host_os, OS_EMOJI["other"])


def _highlight_color(value: object) -> str:
    """Map the parent string variation to a supported UI color or none."""
    if not isinstance(value, str):
        return "none"
    candidate = value.strip().lower()
    return candidate if candidate in VALID_COLORS else "none"


def _detail_fields(detail: Any, key: str, value: object, reason: dict[str, Any]) -> dict[str, Any]:
    """One flag's value and reason for the lab drawer."""
    return {
        "key": key,
        "value": value,
        "variationIndex": detail.variation_index if detail is not None else None,
        "reason": reason,
    }


def evaluate_prerequisite_flags(
    client: Any, username: str
) -> dict[str, Any]:
    """Evaluate the parent and both children; LaunchDarkly enforces each dependency.

    The application calls variation_detail for both children even when the
    parent is off or non-green. A PREREQUISITE_FAILED reason on each child
    proves the dependency came from flag configuration.

    LaunchDarkly: flag prerequisites · evaluation reasons
    https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    """
    user_key = normalize_username(username)
    context = Context.builder(user_key).kind("user").build()
    host_os = detect_host_os()

    if client is None:
        parent_detail = child_detail = emoji_detail = None
        parent_value: object = "none"
        child_value = emoji_value = False
        parent_reason = child_reason = emoji_reason = {"kind": "OFFLINE"}
    else:
        # Same user context for all three. The emoji cites 102; anonymity stays in 102.
        parent_detail = client.variation_detail(FLAG_HIGHLIGHT, context, "none")
        child_detail = client.variation_detail(FLAG_COUNT, context, False)
        emoji_detail = client.variation_detail(FLAG_EMOJI, context, False)
        parent_value = parent_detail.value
        child_value = bool(child_detail.value)
        emoji_value = bool(emoji_detail.value)
        parent_reason = _reason_payload(parent_detail.reason)
        child_reason = _reason_payload(child_detail.reason)
        emoji_reason = _reason_payload(emoji_detail.reason)

    # Green is the required parent variation. Either child's reason can show
    # that LaunchDarkly rejected the dependency.
    prerequisite_met = (
        client is not None
        and parent_value == "green"
        and child_reason.get("kind") != "PREREQUISITE_FAILED"
        and emoji_reason.get("kind") != "PREREQUISITE_FAILED"
    )
    return {
        "username": user_key,
        "highlightColor": _highlight_color(parent_value),
        "showMoveCount": child_value,
        "showHostEmoji": emoji_value,
        "hostOs": host_os,
        "hostEmoji": host_emoji(emoji_value, host_os),
        "prerequisiteMet": prerequisite_met,
        "ldContext": {"kind": "user", "key": user_key},
        "parent": _detail_fields(parent_detail, FLAG_HIGHLIGHT, parent_value, parent_reason),
        "child": _detail_fields(child_detail, FLAG_COUNT, child_value, child_reason),
        "emoji": _detail_fields(emoji_detail, FLAG_EMOJI, emoji_value, emoji_reason),
    }
