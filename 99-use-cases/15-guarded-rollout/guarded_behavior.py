"""Simulated guarded-release behavior when the highlight flag serves green.

In this example, guarded rollout adds metric checks on top of the 15-minute
progressive schedule (10%, 20%, 30%, 50% green highlight):

- Latency: navigation delay 0–1000 ms; threshold 200 ms (max 10% of moves may exceed)
- Error rate: 5% chance of incorrect highlight color; threshold 0% (any error fails)
- Movement: minimum 1 navigation per test; harness skips navigation 5% of the time
"""

from __future__ import annotations

import random
import time
from typing import Any

from metric_events import track_guardrail_events

# LaunchDarkly capability: Guarded rollout metric guardrails
# See: https://launchdarkly.com/docs/home/releases/guarded-rollouts

LATENCY_THRESHOLD_MS = 200
LATENCY_FAIL_TOLERANCE = 0.10
ERROR_COLOR_CHANCE = 0.05
MIN_NAVIGATIONS = 5
MOVEMENT_THRESHOLD = 1
SKIP_NAV_CHANCE = 0.05
MAX_LATENCY_MS = 1000
WRONG_COLORS = ("yellow", "red", "blue", "purple")


def is_flag_enabled(highlight_color: str) -> bool:
    return highlight_color == "green"


def rng_for(username: str, seed: int | None = None) -> random.Random:
    if seed is not None:
        return random.Random(seed)
    return random.Random(hash(username) & 0xFFFFFFFF)


def sample_latency_ms(rng: random.Random) -> int:
    return rng.randint(0, MAX_LATENCY_MS)


def apply_latency_delay(ms: int) -> None:
    if ms > 0:
        time.sleep(ms / 1000.0)


def sample_display_color(expected: str, rng: random.Random) -> tuple[str, bool]:
    if expected != "green":
        return expected, True
    if rng.random() < ERROR_COLOR_CHANCE:
        wrong = rng.choice(WRONG_COLORS)
        return wrong, False
    return expected, True


def should_skip_navigation(rng: random.Random) -> bool:
    return rng.random() < SKIP_NAV_CHANCE


def assess_latency(latency_ms: list[int], flag_enabled: bool) -> tuple[int, bool]:
    if not flag_enabled or not latency_ms:
        return 0, False
    failures = sum(1 for ms in latency_ms if ms >= LATENCY_THRESHOLD_MS)
    fail_rate = failures / len(latency_ms)
    return failures, fail_rate > LATENCY_FAIL_TOLERANCE


def exercise_session(
    flags: dict[str, Any],
    *,
    skip_navigation: bool | None = None,
    seed: int | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Simulate navigations for the guarded-rollout test harness."""
    username = str(flags.get("username", ""))
    expected = str(flags.get("highlightColor", "none"))
    flag_enabled = is_flag_enabled(expected)
    rng = rng_for(username, seed)

    if skip_navigation is None:
        skip_navigation = should_skip_navigation(rng)

    result: dict[str, Any] = {
        **flags,
        "expectedColor": expected,
        "skippedNavigation": skip_navigation,
        "guardrailsActive": flag_enabled,
    }

    if skip_navigation:
        result.update(
            {
                "navigations": 0,
                "latencyMs": [],
                "latencyFailures": 0,
                "latencyFailure": False,
                "displayedColors": [],
                "colorErrors": 0,
                "errorRateFailure": False,
                "movementFailure": True,
            }
        )
        track_guardrail_events(
            client,
            username,
            latency_ms=[],
            color_errors=0,
            navigations=0,
            flag_enabled=flag_enabled,
        )
        return result

    latency_ms: list[int] = []
    displayed_colors: list[str] = []
    color_errors = 0

    for _ in range(MIN_NAVIGATIONS):
        if flag_enabled:
            ms = sample_latency_ms(rng)
            apply_latency_delay(ms)
            latency_ms.append(ms)
            displayed, correct = sample_display_color(expected, rng)
            displayed_colors.append(displayed)
            if not correct:
                color_errors += 1
        else:
            latency_ms.append(0)
            displayed_colors.append(expected)

    latency_failures, latency_failure = assess_latency(latency_ms, flag_enabled)

    result.update(
        {
            "navigations": MIN_NAVIGATIONS,
            "latencyMs": latency_ms,
            "latencyFailures": latency_failures,
            "latencyFailure": latency_failure,
            "displayedColors": displayed_colors,
            "colorErrors": color_errors,
            "errorRateFailure": flag_enabled and color_errors > 0,
            "movementFailure": MIN_NAVIGATIONS < MOVEMENT_THRESHOLD,
        }
    )
    track_guardrail_events(
        client,
        username,
        latency_ms=latency_ms,
        color_errors=color_errors,
        navigations=MIN_NAVIGATIONS,
        flag_enabled=flag_enabled,
    )
    return result


def navigation_display_color(expected: str, rng: random.Random) -> tuple[str, bool]:
    """Pick display color for one interactive navigation when guardrails are active."""
    return sample_display_color(expected, rng)
