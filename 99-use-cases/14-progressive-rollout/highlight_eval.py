"""Evaluate configure-grid-selection-green-highlight for grid highlight color.

In this example, we have a progressive rollout over 15 minutes in five equal stages:
10%, 20%, 40%, 60%, and 100% of users receive the green highlight.
"""

from __future__ import annotations

from ldclient import Context

# LaunchDarkly capability: String flag evaluation (server-side SDK)
# See: https://launchdarkly.com/docs/sdk/features/evaluations

# LaunchDarkly: flag key=configure-grid-selection-green-highlight name="Configure: grid selection green highlight" kind=boolean
# https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-grid-selection-green-highlight

FLAG_HIGHLIGHT = "configure-grid-selection-green-highlight"

VALID_COLORS = frozenset({"yellow", "red", "blue", "green", "purple"})


def build_context(username: str) -> Context:
    """User context keyed by login username."""
    return Context.builder(username).build()


def normalize_highlight_color(raw: object) -> str:
    color = str(raw or "none").strip().lower()
    if color in VALID_COLORS:
        return color
    return "none"


def color_label(highlight_color: str) -> str:
    return f"({highlight_color})" if highlight_color != "none" else "(no-color)"


def build_response(username: str, raw: object) -> dict[str, object]:
    color = normalize_highlight_color(raw)
    return {
        "username": username,
        "flagValue": str(raw if raw is not None else "none"),
        "highlightColor": color,
        "colorLabel": color_label(color),
    }


def evaluate_highlight(client, username: str) -> dict[str, object]:
    context = build_context(username)
    if client is None or not client.is_initialized():
        return build_response(username, "none")
    raw = client.variation(FLAG_HIGHLIGHT, context, "none")
    return build_response(username, raw)
