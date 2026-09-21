"""LaunchDarkly evaluation helpers for the static percentage-rollout lesson."""

from __future__ import annotations

from typing import Any

from ldclient.client import LDClient
from ldclient.context import Context

FLAG_KEY = "enable-grid-selection-highlight-pct"
DEFAULT_VALUE = "none"


def normalize_username(value: str) -> str:
    """Use the trimmed login name as the stable LaunchDarkly context key."""
    username = value.strip()
    if not username:
        raise ValueError("Username is required.")
    return username


def evaluate_rollout(client: LDClient | None, username: str) -> dict[str, Any]:
    """Evaluate the static rollout without implementing bucketing in app code.

    LaunchDarkly percentage rollout:
    https://launchdarkly.com/docs/home/flags/rollouts
    """
    username = normalize_username(username)
    context = Context.builder(username).kind("user").name(username).build()

    if client is None or not client.is_initialized():
        return {
            "flagKey": FLAG_KEY,
            "flagValue": DEFAULT_VALUE,
            "highlightColor": DEFAULT_VALUE,
            "variationIndex": None,
            "reason": {"kind": "ERROR", "errorKind": "CLIENT_NOT_READY"},
            "ldContext": {"kind": "user", "key": username, "name": username},
            "stickyNote": "Safe SDK default; LaunchDarkly client is not ready.",
        }

    detail = client.variation_detail(FLAG_KEY, context, DEFAULT_VALUE)
    value = detail.value if detail.value in {"none", "green"} else DEFAULT_VALUE
    return {
        "flagKey": FLAG_KEY,
        "flagValue": value,
        "highlightColor": value,
        "variationIndex": detail.variation_index,
        "reason": detail.reason,
        "ldContext": {"kind": "user", "key": username, "name": username},
        "stickyNote": (
            "LaunchDarkly buckets this user context key deterministically. "
            "The same key keeps the same assignment while weights stay unchanged."
        ),
    }
