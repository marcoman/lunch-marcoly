"""Resolve grid selection highlight color and cohort label from username context."""

from __future__ import annotations

FLAG_HIGHLIGHT = "configure-grid-selection-green-highlight"
FLAG_CONTEXT = "configure-grid-selection-context-highlight"
FLAG_COUNT = "show-navigation-move-count"

VALID_COLORS = frozenset({"pink", "yellow", "red", "blue", "green", "purple", "none"})


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


def resolve_highlight_color(
    username: str, highlight_enabled: bool, context_highlight: bool
) -> str:
    """Return highlight_color; 'none' when highlight is disabled."""
    if not highlight_enabled:
        return "none"

    if not context_highlight:
        return "pink"

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
    return "pink"


def build_flag_response(
    username: str,
    highlight_enabled: bool,
    context_highlight: bool,
    show_move_count: bool,
) -> dict[str, object]:
    color = resolve_highlight_color(username, highlight_enabled, context_highlight)
    label = format_cohort_label(username, color, context_highlight)
    return {
        "highlightEnabled": highlight_enabled,
        "contextHighlight": context_highlight,
        "showMoveCount": show_move_count,
        "highlightColor": color,
        "cohortLabel": label,
    }
