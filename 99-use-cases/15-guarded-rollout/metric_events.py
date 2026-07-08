"""LaunchDarkly custom metric keys and event tracking for guarded rollout.

In this example, guarded rollout monitors three metrics:

- grid-nav-latency — navigation latency (ms); threshold 200 ms
- grid-highlight-error-rate — incorrect highlight color events; threshold 0%
- grid-nav-movement — navigation count per session; threshold 1
"""

from __future__ import annotations

from typing import Any

from highlight_eval import build_context

# LaunchDarkly capability: Custom metrics + track events
# See: https://launchdarkly.com/docs/home/metrics/custom-metrics

METRIC_KEY_LATENCY = "grid-nav-latency"
METRIC_KEY_ERROR_RATE = "grid-highlight-error-rate"
METRIC_KEY_MOVEMENT = "grid-nav-movement"

EVENT_LATENCY = "grid-navigation-latency"
EVENT_COLOR_ERROR = "grid-highlight-color-error"
EVENT_MOVEMENT = "grid-navigation-count"

METRIC_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "key": METRIC_KEY_LATENCY,
        "name": "Grid navigation latency",
        "description": (
            "Milliseconds from navigation input to grid update when green highlight "
            "is enabled. Guardrail threshold: 200 ms."
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
    },
    {
        "key": METRIC_KEY_ERROR_RATE,
        "name": "Grid highlight error rate",
        "description": (
            "Incorrect highlight color displayed when green highlight is enabled. "
            "Guardrail threshold: 0% error rate."
        ),
        "kind": "custom",
        "isNumeric": False,
        "eventKey": EVENT_COLOR_ERROR,
        "successCriteria": "LowerThanBaseline",
        "analysisUnits": ["user"],
        "tags": ["grid-navigator", "use-case", "guarded-rollout", "error-rate"],
    },
    {
        "key": METRIC_KEY_MOVEMENT,
        "name": "Grid navigation movement",
        "description": (
            "Number of grid navigations per user session. "
            "Guardrail threshold: at least 1 navigation."
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
    },
)


def track_guardrail_events(
    client,
    username: str,
    *,
    latency_ms: list[int],
    color_errors: int,
    navigations: int,
    flag_enabled: bool,
) -> None:
    """Send custom events to LaunchDarkly for guarded rollout metrics."""
    if client is None or not client.is_initialized() or not flag_enabled:
        return

    context = build_context(username)
    for ms in latency_ms:
        client.track(EVENT_LATENCY, context, None, ms)
    for _ in range(color_errors):
        client.track(EVENT_COLOR_ERROR, context)
    client.track(EVENT_MOVEMENT, context, None, navigations)
    client.flush()
