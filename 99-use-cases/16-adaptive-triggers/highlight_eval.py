"""Evaluate the adaptive grid highlight for one LaunchDarkly context."""

from __future__ import annotations

from typing import Any

from ldclient import Context

# Feature flags — server-side string variation
# https://launchdarkly.com/docs/sdk/features/evaluations
FLAG_HIGHLIGHT = "enable-adaptive-grid-highlight"
VALID_COLORS = frozenset({"green"})


def build_context(username: str) -> Context:
    """Build the user context used for flag evaluation and metric events."""
    return Context.builder(username).build()


def build_response(username: str, raw: object) -> dict[str, str]:
    """Normalize an evaluated string variation into the browser API contract."""
    value = str(raw if raw is not None else "none").strip().lower()
    highlight_color = value if value in VALID_COLORS else "none"
    return {
        "username": username,
        "flagValue": value,
        "highlightColor": highlight_color,
        "colorLabel": (
            "(no-color)" if highlight_color == "none" else f"({highlight_color})"
        ),
    }


def evaluate_highlight(client: Any, username: str) -> dict[str, str]:
    """Evaluate the flag, retaining `none` as the code fallback."""
    if client is None or not client.is_initialized():
        return build_response(username, "none")
    raw = client.variation(FLAG_HIGHLIGHT, build_context(username), "none")
    return build_response(username, raw)
