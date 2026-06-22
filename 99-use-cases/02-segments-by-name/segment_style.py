"""Map segment types and flag variations to UI highlight styling."""

from __future__ import annotations

from segment_context import (
    FLAG_HIGHLIGHT,
    SEGMENT_GENERIC,
    SEGMENT_HUMAN,
    SEGMENT_HUMAN_BETA,
    SEGMENT_NAMED_COLOR,
    SEGMENT_ROBOT,
    SEGMENT_ROBOT_BETA,
    SegmentInfo,
    build_segment_context,
)

# LaunchDarkly capability: String flag variation from segment targeting
# See: https://launchdarkly.com/docs/home/flags/segments

VALID_COLORS = frozenset({"yellow", "red", "blue", "green", "purple"})

SEGMENT_HIGHLIGHT_COLORS = {
    SEGMENT_HUMAN: "yellow",
    SEGMENT_ROBOT: "red",
    SEGMENT_HUMAN_BETA: "green",
    SEGMENT_ROBOT_BETA: "purple",
}


def color_label_name(highlight_color: str) -> str:
    return highlight_color if highlight_color != "none" else "no-color"


def format_segment_label(info: SegmentInfo, highlight_color: str) -> str:
    color_name = color_label_name(highlight_color)
    if info.segment_type == SEGMENT_GENERIC:
        return "(generic)"
    if info.segment_type == SEGMENT_NAMED_COLOR:
        return f"({color_name})"
    if info.segment_type in (SEGMENT_HUMAN, SEGMENT_ROBOT):
        return f"({info.segment_type}-{color_name})"
    if info.segment_type in (SEGMENT_HUMAN_BETA, SEGMENT_ROBOT_BETA):
        return f"({info.segment_type}-{color_name})"
    return f"({color_name})"


def normalize_highlight_color(raw: object) -> str:
    color = str(raw or "none").strip().lower()
    if color in VALID_COLORS:
        return color
    return "none"


def expected_color_for_segment(info: SegmentInfo) -> str:
    if info.segment_type == SEGMENT_GENERIC:
        return "none"
    if info.segment_type == SEGMENT_NAMED_COLOR and info.named_color:
        return info.named_color
    return SEGMENT_HIGHLIGHT_COLORS.get(info.segment_type, "none")


def resolve_variation_color(raw: object, info: SegmentInfo) -> str:
    """Map SDK variation to a display color (handles string and legacy boolean flags)."""
    color = normalize_highlight_color(raw)
    if color != "none":
        return color
    # Legacy boolean flag from 10-flag-enablement: true = highlight on, no color string.
    if raw is True:
        return expected_color_for_segment(info)
    return "none"


def build_flag_response(username: str, highlight_color: str, info: SegmentInfo) -> dict[str, object]:
    color = normalize_highlight_color(highlight_color)
    return {
        "highlightColor": color,
        "segmentLabel": format_segment_label(info, color),
        "segmentType": info.segment_type,
    }


def evaluate_highlight(client, username: str) -> dict[str, object]:
    context, info = build_segment_context(username)
    if client is None or not client.is_initialized():
        return build_flag_response(username, "none", info)
    raw = client.variation(FLAG_HIGHLIGHT, context, "none")
    color = resolve_variation_color(raw, info)
    return build_flag_response(username, color, info)
