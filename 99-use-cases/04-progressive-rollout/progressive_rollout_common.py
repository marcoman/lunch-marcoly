"""Shared progressive rollout configuration and LaunchDarkly REST helpers."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# In this example, we have a progressive rollout over 15 minutes in five equal
# stages: 10%, 20%, 40%, 60%, and 100% of users receive the green highlight.

# LaunchDarkly capability: Percentage rollout on fallthrough rule
# See: https://launchdarkly.com/docs/home/releases/progressive-rollouts

FLAG_KEY = "configure-grid-selection-green-highlight"
ROLLOUT_COLOR = "green"
BASELINE_COLOR = "none"

# Five equal segments over 15 minutes (3 minutes each).
ROLLOUT_DURATION_MINUTES = 15
ROLLOUT_STAGE_COUNT = 5
STAGE_DURATION_SECONDS = (ROLLOUT_DURATION_MINUTES * 60) // ROLLOUT_STAGE_COUNT
ROLLOUT_PERCENTAGES = [10, 20, 40, 60, 100]


def api_request(method: str, path: str, body: dict | None = None) -> dict:
    api_host = os.environ.get("LD_API_HOST", "https://app.launchdarkly.com")
    token = os.environ.get("LD_API_ACCESS_TOKEN")
    project = os.environ.get("LD_PROJECT_KEY")
    if not token or not project:
        raise SystemExit("LD_API_ACCESS_TOKEN and LD_PROJECT_KEY are required")

    url = f"{api_host}/api/v2{path}"
    headers = {
        "Authorization": token,
        "LD-API-Version": os.environ.get("LD_API_VERSION", "20240415"),
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json; domain-model=launchdarkly.semanticpatch"
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"LaunchDarkly API error {exc.code}: {detail}") from exc


def fetch_flag() -> dict:
    project = os.environ["LD_PROJECT_KEY"]
    return api_request("GET", f"/flags/{project}/{FLAG_KEY}")


def require_environment_key(flag: dict) -> str:
    env_key = os.environ.get("LD_ENVIRONMENT_KEY", "").strip()
    if not env_key:
        raise SystemExit(
            "LD_ENVIRONMENT_KEY is required. "
            "Set it to the environment key shown in LaunchDarkly (e.g. test, production)."
        )
    environments = flag.get("environments", {})
    if env_key not in environments:
        available = ", ".join(sorted(environments.keys())) or "(none)"
        raise SystemExit(
            f"LD_ENVIRONMENT_KEY={env_key!r} was not found.\n"
            f"Available environments: {available}"
        )
    return env_key


def variation_id(flag: dict, value: str) -> str:
    for item in flag.get("variations", []):
        if str(item.get("value")) == value:
            var_id = item.get("_id")
            if var_id:
                return str(var_id)
    raise SystemExit(f"Variation {value!r} not found on flag {FLAG_KEY}")


def apply_rollout_percent(green_percent: int, env_key: str, comment: str) -> dict:
    if not 0 <= green_percent <= 100:
        raise ValueError("green_percent must be between 0 and 100")

    flag = fetch_flag()
    green_id = variation_id(flag, ROLLOUT_COLOR)
    none_id = variation_id(flag, BASELINE_COLOR)
    project = os.environ["LD_PROJECT_KEY"]

    if green_percent == 0:
        instructions = [{"kind": "turnFlagOff"}]
    elif green_percent == 100:
        instructions = [
            {"kind": "turnFlagOn"},
            {"kind": "updateFallthroughVariationOrRollout", "variationId": green_id},
        ]
    else:
        none_percent = 100 - green_percent
        rollout_weights = {
            green_id: green_percent * 1000,
            none_id: none_percent * 1000,
        }
        instructions = [
            {"kind": "turnFlagOn"},
            {
                "kind": "updateFallthroughVariationOrRollout",
                "rolloutContextKind": "user",
                "rolloutWeights": rollout_weights,
            },
        ]

    body = {
        "environmentKey": env_key,
        "comment": comment,
        "instructions": instructions,
    }
    return api_request("PATCH", f"/flags/{project}/{FLAG_KEY}", body)


def rollout_schedule_summary() -> str:
    lines = [
        f"Progressive rollout: {ROLLOUT_DURATION_MINUTES} minutes, "
        f"{ROLLOUT_STAGE_COUNT} equal stages ({STAGE_DURATION_SECONDS // 60} min each)",
    ]
    for i, pct in enumerate(ROLLOUT_PERCENTAGES, start=1):
        start_min = (i - 1) * STAGE_DURATION_SECONDS // 60
        end_min = i * STAGE_DURATION_SECONDS // 60
        lines.append(f"  Stage {i} ({start_min:02d}:00–{end_min:02d}:00): {pct}% → {ROLLOUT_COLOR}")
    return "\n".join(lines)


def _variation_values(flag: dict) -> list[str]:
    return [str(v.get("value", "")).lower() for v in flag.get("variations", [])]


def _green_percent_from_fallthrough(flag: dict, fallthrough: dict) -> float | None:
    """Return configured green traffic % from fallthrough, or None if not parseable."""
    values = _variation_values(flag)
    if not values:
        return None

    if "variation" in fallthrough:
        idx = fallthrough["variation"]
        if not isinstance(idx, int) or idx >= len(values):
            return None
        value = values[idx]
        if value == ROLLOUT_COLOR:
            return 100.0
        if value == BASELINE_COLOR:
            return 0.0
        return None

    rollout = fallthrough.get("rollout")
    if not isinstance(rollout, dict):
        return None

    green_percent = 0.0
    for entry in rollout.get("variations", []):
        idx = entry.get("variation")
        weight = entry.get("weight", 0)
        if not isinstance(idx, int) or idx >= len(values):
            continue
        if values[idx] == ROLLOUT_COLOR:
            green_percent += weight / 1000.0
    return green_percent


def match_rollout_stage(green_percent: float) -> tuple[int, int]:
    """Map a configured green % to the nearest stage (number, target %)."""
    if green_percent <= 0:
        return 0, 0
    for stage, target in enumerate(ROLLOUT_PERCENTAGES, start=1):
        if abs(green_percent - target) < 0.5:
            return stage, target
    nearest = min(
        enumerate(ROLLOUT_PERCENTAGES, start=1),
        key=lambda item: abs(green_percent - item[1]),
    )
    return nearest[0], nearest[1]


def query_rollout_state() -> dict[str, object]:
    """Query LaunchDarkly for the flag's current rollout configuration."""
    flag = fetch_flag()
    env_key = require_environment_key(flag)
    env = flag.get("environments", {}).get(env_key, {})

    if not env.get("on"):
        return {
            "on": False,
            "greenPercent": 0.0,
            "stage": 0,
            "stageTarget": 0,
            "source": "api",
        }

    fallthrough = env.get("fallthrough", {})
    green_percent = _green_percent_from_fallthrough(flag, fallthrough)
    if green_percent is None:
        return {
            "on": True,
            "greenPercent": None,
            "stage": None,
            "stageTarget": None,
            "source": "api",
        }

    stage, target = match_rollout_stage(green_percent)
    return {
        "on": True,
        "greenPercent": green_percent,
        "stage": stage,
        "stageTarget": target,
        "source": "api",
    }


def try_query_rollout_state() -> dict[str, object] | None:
    """Return rollout state from the API, or None if credentials are unavailable."""
    if not os.environ.get("LD_API_ACCESS_TOKEN") or not os.environ.get("LD_PROJECT_KEY"):
        return None
    try:
        return query_rollout_state()
    except SystemExit:
        return None
