"""Resolve grid selection highlight color and cohort label from username context.

enable-grid-selection-highlight is a string flag (none | colors).
Legacy boolean true/false is still accepted by interpret_highlight_variation.

LaunchDarkly: feature flags — multivariate string variations
https://launchdarkly.com/docs/home/flags/concepts
"""

from __future__ import annotations

from host_os import os_emoji_for

# LaunchDarkly: flag key=enable-grid-selection-highlight
# name="Enable: grid selection highlight" kind=string
# https://app.launchdarkly.com/projects/lunch-marcoly/features/enable-grid-selection-highlight

FLAG_HIGHLIGHT = "enable-grid-selection-highlight"
# LaunchDarkly: flag key=enable-grid-highlight-color-override
# name="Enable: grid highlight color override" kind=boolean
# https://app.launchdarkly.com/projects/lunch-marcoly/features/enable-grid-highlight-color-override

FLAG_CONTEXT = "enable-grid-highlight-color-override"
# LaunchDarkly: flag key=show-navigation-move-count
# https://app.launchdarkly.com/projects/lunch-marcoly/features/show-navigation-move-count

FLAG_COUNT = "show-navigation-move-count"

VALID_COLORS = frozenset({"pink", "yellow", "red", "blue", "green", "purple", "none"})

# Prefer green when Controls turns a string highlight flag ON (matches flag name).
DEFAULT_STRING_ON_COLOR = "green"


def parse_cohorts(username: str) -> tuple[bool, bool, bool]:
    lower = username.lower()
    return "human" in lower, "robot" in lower, "beta" in lower


def color_label_name(highlight_color: str) -> str:
    return highlight_color if highlight_color != "none" else "no-color"


def format_cohort_label(
    username: str,
    highlight_color: str,
    context_highlight: bool,
) -> str:
    """Build label like (human-yellow), (human-beta-green), (pink), or (no-color)."""
    color_name = color_label_name(highlight_color)
    parts: list[str] = []
    if context_highlight:
        is_human, is_robot, is_beta = parse_cohorts(username)
        if is_human:
            parts.append("human")
        if is_robot:
            parts.append("robot")
        if is_beta:
            parts.append("beta")
    if parts:
        return f"({'-'.join(parts)}-{color_name})"
    return f"({color_name})"


def is_highlight_off_value(value: object) -> bool:
    """True when the served variation means “no highlight”."""
    if value is False or value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "none", "false", "off"}
    return False


def interpret_highlight_variation(raw: object) -> tuple[bool, str | None]:
    """
    Normalize boolean or string highlight variations.

    Returns (enabled, served_color).
    served_color is set only for string color variations (not pink default).
    """
    if isinstance(raw, bool):
        return raw, None
    if is_highlight_off_value(raw):
        return False, None
    if isinstance(raw, str):
        color = raw.strip().lower()
        if color in VALID_COLORS and color != "none":
            return True, color
        # Unknown non-empty string: treat as enabled; resolve falls back to pink.
        return True, None
    return bool(raw), None


def resolve_highlight_color(
    username: str,
    highlight_enabled: bool,
    context_highlight: bool,
    served_color: str | None = None,
) -> str:
    """Return highlight_color; 'none' when highlight is disabled."""
    if not highlight_enabled:
        return "none"

    if context_highlight:
        is_human, is_robot, is_beta = parse_cohorts(username)
        if is_human and is_beta:
            return "green"
        if is_robot and is_beta:
            return "purple"
        if is_human:
            return "yellow"
        if is_robot:
            return "red"
        if is_beta:
            return "blue"
        # No cohort words: keep served string color when present, else pink.
        if served_color and served_color in VALID_COLORS and served_color != "none":
            return served_color
        return "pink"

    if served_color and served_color in VALID_COLORS and served_color != "none":
        return served_color
    return "pink"


def build_flag_response(
    username: str,
    highlight_enabled: bool,
    context_highlight: bool,
    show_move_count: bool,
    show_os_emoji: bool,
    host_os: str,
    served_color: str | None = None,
) -> dict[str, object]:
    color = resolve_highlight_color(
        username, highlight_enabled, context_highlight, served_color
    )
    label = format_cohort_label(username, color, context_highlight)
    return {
        "highlightEnabled": highlight_enabled,
        "contextHighlight": context_highlight,
        "showMoveCount": show_move_count,
        "highlightColor": color,
        "cohortLabel": label,
        "osEmoji": os_emoji_for(host_os, show_os_emoji),
        "highlightServedValue": served_color if served_color is not None else highlight_enabled,
    }
