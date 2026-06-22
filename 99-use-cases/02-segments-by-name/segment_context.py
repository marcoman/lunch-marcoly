"""Build LaunchDarkly user contexts for segment-by-name targeting."""

from __future__ import annotations

from dataclasses import dataclass

from ldclient import Context

# LaunchDarkly capability: Context attributes for segment rules
# See: https://launchdarkly.com/docs/home/observability/context-kinds

FLAG_HIGHLIGHT = "configure-grid-selection-green-highlight"

COLOR_NAMES = frozenset({"yellow", "red", "blue", "green", "purple"})

SEGMENT_GENERIC = "generic"
SEGMENT_NAMED_COLOR = "named-color"
SEGMENT_HUMAN = "human"
SEGMENT_ROBOT = "robot"
SEGMENT_HUMAN_BETA = "human-beta"
SEGMENT_ROBOT_BETA = "robot-beta"

ALLOWED_SEGMENT_TYPES = frozenset(
    {
        SEGMENT_GENERIC,
        SEGMENT_NAMED_COLOR,
        SEGMENT_HUMAN,
        SEGMENT_ROBOT,
        SEGMENT_HUMAN_BETA,
        SEGMENT_ROBOT_BETA,
    }
)


@dataclass(frozen=True)
class SegmentInfo:
    segment_type: str
    named_color: str | None = None


def letter_count(username: str) -> int:
    return sum(1 for ch in username if ch.isalpha())


def resolve_segment_info(username: str) -> SegmentInfo:
    """Derive segment type from username using priority rules (early exit)."""
    lower = username.lower()

    if lower == "generic":
        return SegmentInfo(SEGMENT_GENERIC)

    if lower in COLOR_NAMES:
        return SegmentInfo(SEGMENT_NAMED_COLOR, named_color=lower)

    is_human = letter_count(username) % 2 == 0
    is_beta = "beta" in lower

    if is_human and is_beta:
        return SegmentInfo(SEGMENT_HUMAN_BETA)
    if is_human:
        return SegmentInfo(SEGMENT_HUMAN)
    if is_beta:
        return SegmentInfo(SEGMENT_ROBOT_BETA)
    return SegmentInfo(SEGMENT_ROBOT)


def build_segment_context(username: str) -> tuple[Context, SegmentInfo]:
    """Return an LD user context with attributes segments match on."""
    info = resolve_segment_info(username)
    builder = Context.builder(username).set("segmentType", info.segment_type)

    if info.segment_type == SEGMENT_GENERIC:
        builder.set("generic", True)
    elif info.segment_type == SEGMENT_NAMED_COLOR and info.named_color:
        builder.set("namedColor", info.named_color)
    else:
        user_kind = "human" if info.segment_type.startswith("human") else "robot"
        builder.set("userKind", user_kind)
        if info.segment_type.endswith("beta"):
            builder.set("beta", True)
        else:
            builder.set("beta", False)

    return builder.build(), info
