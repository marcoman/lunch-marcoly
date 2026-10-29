"""Evaluate api-progressive-grid-highlight for one username.

The schedule lives in an environment release, not in this process.
rest/start-progressive-release.sh starts that release. This function
only reads the variation the SDK returns.

LaunchDarkly: string flag variation
https://launchdarkly.com/docs/sdk/features/evaluations
"""

from __future__ import annotations

from ldclient import Context

FLAG_HIGHLIGHT = "api-progressive-grid-highlight"
DEFAULT_VALUE = "none"
VALID_COLORS = frozenset({"yellow", "red", "blue", "green", "purple"})


def build_context(username: str) -> Context:
    """User context. The release rule matches this kind."""
    return Context.builder(username).kind("user").name(username).build()


def normalize_highlight_color(raw: object) -> str:
    color = str(raw or DEFAULT_VALUE).strip().lower()
    if color in VALID_COLORS:
        return color
    return DEFAULT_VALUE


def color_label(highlight_color: str) -> str:
    return f"({highlight_color})" if highlight_color != DEFAULT_VALUE else "(no-color)"


def build_response(
    username: str,
    raw: object,
    reason: dict | None = None,
    variation_index: int | None = None,
) -> dict[str, object]:
    color = normalize_highlight_color(raw)
    return {
        "username": username,
        "flagKey": FLAG_HIGHLIGHT,
        "flagValue": str(raw if raw is not None else DEFAULT_VALUE),
        "highlightColor": color,
        "colorLabel": color_label(color),
        "variationIndex": variation_index,
        "reason": reason or {"kind": "ERROR", "errorKind": "CLIENT_NOT_READY"},
        "ldContext": {"kind": "user", "key": username, "name": username},
    }


def evaluate_highlight(client, username: str) -> dict[str, object]:
    """Read the highlight variation for this user context.

    LaunchDarkly: variation detail — value plus the reason kind.
    https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    """
    if client is None or not client.is_initialized():
        return build_response(username, DEFAULT_VALUE)
    detail = client.variation_detail(FLAG_HIGHLIGHT, build_context(username), DEFAULT_VALUE)
    reason = detail.reason if isinstance(detail.reason, dict) else {"kind": "UNKNOWN"}
    return build_response(username, detail.value, reason, detail.variation_index)
