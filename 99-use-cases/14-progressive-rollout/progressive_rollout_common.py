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


def _rollout_allocation_type(fallthrough: dict) -> str | None:
    rollout = fallthrough.get("rollout")
    if not isinstance(rollout, dict):
        return None
    experiment = rollout.get("experimentAllocation", {})
    if not isinstance(experiment, dict):
        return None
    rollout_type = experiment.get("type")
    return str(rollout_type) if rollout_type else None


def _is_measured_rollout(fallthrough: dict) -> bool:
    """Guarded rollouts in the UI use experimentAllocation.type measuredRollout."""
    return _rollout_allocation_type(fallthrough) == "measuredRollout"


def _is_progressive_rollout_ui(fallthrough: dict) -> bool:
    """True when the UI has an active or configured progressive rollout on this rule."""
    if _rollout_allocation_type(fallthrough) == "progressiveRollout":
        return True
    return isinstance(fallthrough.get("progressiveRolloutConfig"), dict)


def _green_variation_index(flag: dict) -> int | None:
    values = _variation_values(flag)
    for i, value in enumerate(values):
        if value == ROLLOUT_COLOR:
            return i
    return None


def _green_percent_from_rollout(
    flag: dict,
    rollout: dict,
    *,
    tracked_only: bool,
) -> float | None:
    green_idx = _green_variation_index(flag)
    if green_idx is None:
        return None

    green_percent = 0.0
    found = False
    for entry in rollout.get("variations", []):
        if entry.get("variation") != green_idx:
            continue
        if tracked_only and entry.get("_untracked") is True:
            continue
        weight = entry.get("weight", 0)
        if isinstance(weight, (int, float)):
            green_percent += weight / 1000.0
            found = True
    return green_percent if found else None


def _stage_targets_from_progressive_config(config: dict) -> list[int]:
    targets: list[int] = []
    for step in config.get("steps", []):
        if not isinstance(step, dict):
            continue
        weight = step.get("rolloutWeight")
        if isinstance(weight, (int, float)):
            targets.append(int(round(weight / 1000.0 if weight > 100 else weight)))
    return targets or ROLLOUT_PERCENTAGES


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

    tracked_only = _is_measured_rollout(fallthrough) or _is_progressive_rollout_ui(fallthrough)
    return _green_percent_from_rollout(flag, rollout, tracked_only=tracked_only)


def match_rollout_stage(
    green_percent: float,
    stage_targets: list[int] | None = None,
) -> tuple[int, int]:
    """Map a configured green % to the nearest stage (number, target %)."""
    targets = stage_targets or ROLLOUT_PERCENTAGES
    if green_percent <= 0:
        return 0, 0
    for stage, target in enumerate(targets, start=1):
        if abs(green_percent - target) < 0.5:
            return stage, target
    nearest = min(
        enumerate(targets, start=1),
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
            "rolloutType": "off",
            "allocationType": None,
            "greenPercent": 0.0,
            "stage": 0,
            "stageTarget": 0,
            "source": "api",
        }

    fallthrough = env.get("fallthrough", {})
    allocation_type = _rollout_allocation_type(fallthrough)
    stage_targets = ROLLOUT_PERCENTAGES
    progressive_config = fallthrough.get("progressiveRolloutConfig")
    if isinstance(progressive_config, dict):
        stage_targets = _stage_targets_from_progressive_config(progressive_config)

    if _is_measured_rollout(fallthrough):
        green_percent = _green_percent_from_fallthrough(flag, fallthrough)
        stage, target = (
            match_rollout_stage(green_percent, stage_targets)
            if green_percent is not None
            else (None, None)
        )
        return {
            "on": True,
            "rolloutType": "guarded",
            "allocationType": allocation_type,
            "greenPercent": green_percent,
            "stage": stage,
            "stageTarget": target,
            "source": "api",
        }

    if _is_progressive_rollout_ui(fallthrough):
        green_percent = _green_percent_from_fallthrough(flag, fallthrough)
        stage, target = (
            match_rollout_stage(green_percent, stage_targets)
            if green_percent is not None
            else (None, None)
        )
        return {
            "on": True,
            "rolloutType": "progressive",
            "allocationType": allocation_type,
            "greenPercent": green_percent,
            "stage": stage,
            "stageTarget": target,
            "source": "api",
        }

    green_percent = _green_percent_from_fallthrough(flag, fallthrough)
    if green_percent is None:
        return {
            "on": True,
            "rolloutType": "unknown",
            "allocationType": allocation_type,
            "greenPercent": None,
            "stage": None,
            "stageTarget": None,
            "source": "api",
        }

    if "rollout" in fallthrough:
        rollout_type = "percentage"
    else:
        rollout_type = "fixed"

    stage, target = match_rollout_stage(green_percent, stage_targets)
    return {
        "on": True,
        "rolloutType": rollout_type,
        "allocationType": allocation_type,
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
