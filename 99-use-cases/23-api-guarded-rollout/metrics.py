"""Guardrail metrics for the guarded environment release.

Same three checks as 15-guarded-rollout, on the same metric keys.
Latency is the lever: the slider sets the milliseconds. Error rate
stays quiet. Movement sends one navigation so it stays in range.

LaunchDarkly: custom metrics
https://launchdarkly.com/docs/home/metrics/custom-metrics
"""

from __future__ import annotations

from typing import Any

from highlight_eval import build_context, evaluate_highlight

# Same keys example 15 already tested. Descriptions here are the 23 wording.
METRIC_KEY_LATENCY = "grid-nav-latency"
METRIC_KEY_ERROR_RATE = "grid-highlight-error-rate"
METRIC_KEY_MOVEMENT = "grid-nav-movement"

EVENT_LATENCY = "grid-navigation-latency"
EVENT_COLOR_ERROR = "grid-highlight-color-error"
EVENT_MOVEMENT = "grid-navigation-count"

LATENCY_THRESHOLD_MS = 200
# Contexts still on none report this. The slider applies only to green.
HEALTHY_LATENCY_MS = 50
# One login is one bucket. A small fixed set gives both variations events.
SAMPLE_COUNT = 24

METRIC_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "key": METRIC_KEY_LATENCY,
        "name": "Grid navigation latency",
        "description": (
            "Milliseconds reported for one grid move. Lower is better. "
            "Above 200 ms is the latency guardrail. "
            "In 23-api-guarded-rollout, contexts receiving green send the slider value "
            "and contexts still on none send 50 ms, so a high slider makes the new variation look slower. "
            "In 15-guarded-rollout a harness draws a random delay."
        ),
        "kind": "custom",
        "isNumeric": True,
        "eventKey": EVENT_LATENCY,
        "unit": "milliseconds",
        "successCriteria": "LowerThanBaseline",
        "analysisUnits": ["user"],
        "unitAggregationType": "average",
        "analysisType": "mean",
        "tags": ["grid-navigator", "use-case", "guarded-rollout", "latency"],
        "role": "violation",
    },
    {
        "key": METRIC_KEY_ERROR_RATE,
        "name": "Grid highlight error rate",
        "description": (
            "One event means the selected cell showed the wrong highlight color. "
            "Lower is better. The guardrail is 0% errors. "
            "23-api-guarded-rollout sends no events, so this guardrail stays normal "
            "while you watch latency."
        ),
        "kind": "custom",
        "isNumeric": False,
        "eventKey": EVENT_COLOR_ERROR,
        "successCriteria": "LowerThanBaseline",
        "analysisUnits": ["user"],
        "tags": ["grid-navigator", "use-case", "guarded-rollout", "error-rate"],
        "role": "normal",
    },
    {
        "key": METRIC_KEY_MOVEMENT,
        "name": "Grid navigation movement",
        "description": (
            "How many times the user moved on the grid. Higher is better. "
            "The guardrail is at least one navigation. "
            "23-api-guarded-rollout sends 1 on each move and each automatic report, "
            "so this guardrail stays normal."
        ),
        "kind": "custom",
        "isNumeric": True,
        "eventKey": EVENT_MOVEMENT,
        "unit": "navigations",
        "successCriteria": "HigherThanBaseline",
        "analysisUnits": ["user"],
        "unitAggregationType": "sum",
        "analysisType": "mean",
        "tags": ["grid-navigator", "use-case", "guarded-rollout", "movement"],
        "role": "normal",
    },
)


def metric_views() -> list[dict[str, str]]:
    """The three guardrails, in the order the page lists them."""
    return [
        {
            "key": item["key"],
            "name": item["name"],
            "eventKey": item["eventKey"],
            "description": item["description"],
            "role": item["role"],
        }
        for item in METRIC_DEFINITIONS
    ]


def create_body(definition: dict[str, Any]) -> dict[str, Any]:
    """Metric create payload. The page-only role field stays out of the API body."""
    return {key: value for key, value in definition.items() if key != "role"}


def sample_usernames(username: str) -> list[str]:
    """The logged-in user, then username-1 … so both variations can receive events."""
    return [username, *[f"{username}-{index}" for index in range(1, SAMPLE_COUNT)]]


def track_observed(client, username: str, latency_ms: float) -> dict[str, object]:
    """Send latency and one navigation. Do not send a color error.

    Green contexts report the slider. None contexts report 50 ms, so a high
    slider makes the new variation look slower than the original.

    LaunchDarkly: custom events with a numeric metric value.
    https://launchdarkly.com/docs/sdk/features/events
    """
    green = 0
    none = 0
    for name in sample_usernames(username):
        served = evaluate_highlight(client, name).get("highlightColor")
        value = latency_ms if served == "green" else float(HEALTHY_LATENCY_MS)
        context = build_context(name)
        client.track(EVENT_LATENCY, context, None, value)
        client.track(EVENT_MOVEMENT, context, None, 1)
        if served == "green":
            green += 1
        else:
            none += 1
    client.flush()
    return {
        "tracked": True,
        "latencyMs": latency_ms,
        "healthyMs": HEALTHY_LATENCY_MS,
        "aboveThreshold": latency_ms > LATENCY_THRESHOLD_MS,
        "greenContexts": green,
        "noneContexts": none,
        "movement": 1,
        "colorErrors": 0,
        "latencyEvent": EVENT_LATENCY,
        "movementEvent": EVENT_MOVEMENT,
    }
