"""Flag variation keys, defaults, and response building for 11-flag-variations."""

from __future__ import annotations

import json
from typing import Any

from host_os import (
    FLAG_ANON_OS_EMOJI,
    build_anonymous_context,
    build_user_context,
    os_emoji_for,
)

# LaunchDarkly capability: Multivariate flag evaluation (string, number, JSON)
# See: https://launchdarkly.com/docs/sdk/features/flag-types

FLAG_COUNT_LABEL = "configure-navigation-count-label"
FLAG_LUCKY_NUMBER = "configure-lucky-number"
FLAG_MAX_MOVES = "configure-max-navigation-moves"

DEFAULT_COUNT_LABEL = "Count"
DEFAULT_LUCKY_NUMBER = 0
DEFAULT_MAX_MOVES = 100


def parse_max_moves(raw: Any) -> int:
    if isinstance(raw, dict):
        return int(raw.get("maxMoves", DEFAULT_MAX_MOVES))
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return int(parsed.get("maxMoves", DEFAULT_MAX_MOVES))
        except json.JSONDecodeError:
            pass
    return DEFAULT_MAX_MOVES


def build_flag_response(
    username: str,
    count_label: str,
    lucky_number: float | int,
    max_moves: int,
    os_emoji: str,
) -> dict[str, Any]:
    return {
        "countLabel": count_label or DEFAULT_COUNT_LABEL,
        "luckyNumber": int(lucky_number),
        "maxMoves": max_moves,
        "osEmoji": os_emoji,
    }


def evaluate_flags(client, username: str, host_os: str) -> dict[str, Any]:
    """Evaluate all four flags; anonymous emoji uses anonymous context."""
    if client is None or not client.is_initialized():
        return build_flag_response(
            username,
            DEFAULT_COUNT_LABEL,
            DEFAULT_LUCKY_NUMBER,
            DEFAULT_MAX_MOVES,
            "",
        )

    anon_context, detected_os = build_anonymous_context()
    user_context = build_user_context(username)
    host = host_os or detected_os

    show_emoji = bool(client.variation(FLAG_ANON_OS_EMOJI, anon_context, False))
    count_label = str(
        client.variation(FLAG_COUNT_LABEL, user_context, DEFAULT_COUNT_LABEL)
    )
    lucky_number = client.variation(FLAG_LUCKY_NUMBER, user_context, DEFAULT_LUCKY_NUMBER)
    max_moves_raw = client.variation(
        FLAG_MAX_MOVES,
        user_context,
        {"maxMoves": DEFAULT_MAX_MOVES},
    )

    return build_flag_response(
        username,
        count_label,
        lucky_number,
        parse_max_moves(max_moves_raw),
        os_emoji_for(host, show_emoji),
    )
