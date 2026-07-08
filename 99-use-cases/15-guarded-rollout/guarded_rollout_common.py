"""Shared guarded rollout configuration and LaunchDarkly REST helpers."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# In this example, we have a guarded rollout over 12 minutes in four equal
# stages: 10%, 20%, 30%, and 50% of users receive the green highlight.

# LaunchDarkly capability: Guarded rollout with metric guardrails
# See: https://launchdarkly.com/docs/home/releases/guarded-rollouts

FLAG_KEY = "configure-grid-selection-green-highlight"
ROLLOUT_COLOR = "green"
BASELINE_COLOR = "none"

# Four equal segments over 12 minutes (3 minutes each).
ROLLOUT_DURATION_MINUTES = 12
ROLLOUT_STAGE_COUNT = 4
STAGE_DURATION_SECONDS = (ROLLOUT_DURATION_MINUTES * 60) // ROLLOUT_STAGE_COUNT
ROLLOUT_PERCENTAGES = [10, 20, 30, 50]

BETA_API_VERSION = "beta"


def api_request(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    api_version: str | None = None,
) -> dict:
    api_host = os.environ.get("LD_API_HOST", "https://app.launchdarkly.com")
    token = os.environ.get("LD_API_ACCESS_TOKEN")
    project = os.environ.get("LD_PROJECT_KEY")
    if not token or not project:
        raise SystemExit("LD_API_ACCESS_TOKEN and LD_PROJECT_KEY are required")

    url = f"{api_host}/api/v2{path}"
    headers = {
        "Authorization": token,
        "LD-API-Version": api_version or os.environ.get("LD_API_VERSION", "20240415"),
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


def fetch_flag_with_guarded_rollout(env_key: str) -> dict:
    """Fetch flag targeting plus active guarded-rollout state (beta expand)."""
    project = os.environ["LD_PROJECT_KEY"]
    path = (
        f"/flags/{project}/{FLAG_KEY}"
        f"?env={env_key}&expand=guardedRollout"
    )
    return api_request("GET", path, api_version=BETA_API_VERSION)


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
        f"Guarded rollout: {ROLLOUT_DURATION_MINUTES} minutes, "
        f"{ROLLOUT_STAGE_COUNT} equal stages ({STAGE_DURATION_SECONDS // 60} min each)",
    ]
    for i, pct in enumerate(ROLLOUT_PERCENTAGES, start=1):
        start_min = (i - 1) * STAGE_DURATION_SECONDS // 60
        end_min = i * STAGE_DURATION_SECONDS // 60
        lines.append(f"  Stage {i} ({start_min:02d}:00–{end_min:02d}:00): {pct}% → {ROLLOUT_COLOR}")
    return "\n".join(lines)


def _variation_values(flag: dict) -> list[str]:
    return [str(v.get("value", "")).lower() for v in flag.get("variations", [])]


def _weight_to_percent(weight: object) -> float | None:
    if not isinstance(weight, (int, float)):
        return None
    value = float(weight)
    if value > 100:
        return value / 1000.0
    return value


def _is_measured_rollout(fallthrough: dict) -> bool:
    """True when the UI has an active guarded rollout on this rule."""
    rollout = fallthrough.get("rollout")
    if not isinstance(rollout, dict):
        return False
    experiment = rollout.get("experimentAllocation", {})
    if not isinstance(experiment, dict):
        return False
    return experiment.get("type") == "measuredRollout"


def _green_percent_from_measured_rollout(flag: dict, rollout: dict) -> float | None:
    """Return green % from a fallthrough measuredRollout (guarded rollout in the UI)."""
    values = _variation_values(flag)
    if not values:
        return None

    green_idx = next(
        (i for i, v in enumerate(values) if v == ROLLOUT_COLOR),
        None,
    )
    if green_idx is None:
        return None

    green_percent = 0.0
    found = False
    for entry in rollout.get("variations", []):
        if entry.get("variation") != green_idx:
            continue
        if entry.get("_untracked") is True:
            continue
        weight = entry.get("weight", 0)
        if isinstance(weight, (int, float)):
            green_percent += weight / 1000.0
            found = True
    return green_percent if found else None


def _stage_targets_from_config(config: dict) -> list[int]:
    targets: list[int] = []
    for stage in config.get("stages", []):
        if not isinstance(stage, dict):
            continue
        pct = _weight_to_percent(stage.get("rolloutWeight"))
        if pct is not None:
            targets.append(int(round(pct)))
    return targets or ROLLOUT_PERCENTAGES


def _green_percent_from_fallthrough(flag: dict, fallthrough: dict) -> float | None:
    """Return configured green traffic % from fallthrough, or None if not parseable."""
    values = _variation_values(flag)
    if not values:
        return None

    config = fallthrough.get("guardedRolloutConfig")
    if isinstance(config, dict):
        end_idx = config.get("endVariation")
        if isinstance(end_idx, int) and end_idx < len(values):
            if values[end_idx] == ROLLOUT_COLOR:
                stages = config.get("stages", [])
                if stages and isinstance(stages[-1], dict):
                    last = _weight_to_percent(stages[-1].get("rolloutWeight"))
                    if last is not None:
                        return last

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

    if _is_measured_rollout(fallthrough):
        measured = _green_percent_from_measured_rollout(flag, rollout)
        if measured is not None:
            return measured

    green_percent = 0.0
    for entry in rollout.get("variations", []):
        idx = entry.get("variation")
        weight = entry.get("weight", 0)
        if not isinstance(idx, int) or idx >= len(values):
            continue
        if values[idx] == ROLLOUT_COLOR:
            green_percent += weight / 1000.0
    return green_percent


def _green_percent_from_guarded_rollout(guarded: dict) -> float | None:
    """Parse current green % from an active guardedRollout expand object."""
    for key in (
        "currentRolloutWeight",
        "rolloutWeight",
        "currentWeight",
        "targetRolloutWeight",
    ):
        pct = _weight_to_percent(guarded.get(key))
        if pct is not None:
            return pct

    stage_idx = guarded.get("currentStageIndex", guarded.get("stageIndex"))
    stages = guarded.get("stages")
    if isinstance(stage_idx, int) and isinstance(stages, list) and stages:
        if 0 <= stage_idx < len(stages) and isinstance(stages[stage_idx], dict):
            pct = _weight_to_percent(stages[stage_idx].get("rolloutWeight"))
            if pct is not None:
                return pct

    config = guarded.get("config") or guarded.get("guardedRolloutConfig")
    if isinstance(config, dict):
        stages = config.get("stages", [])
        stage_idx = guarded.get("currentStageIndex", guarded.get("stageIndex"))
        if isinstance(stage_idx, int) and 0 <= stage_idx < len(stages):
            pct = _weight_to_percent(stages[stage_idx].get("rolloutWeight"))
            if pct is not None:
                return pct
        if stages and isinstance(stages[-1], dict):
            return _weight_to_percent(stages[-1].get("rolloutWeight"))

    return None


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
    env_key = os.environ.get("LD_ENVIRONMENT_KEY", "").strip()
    if not env_key:
        raise SystemExit("LD_ENVIRONMENT_KEY is required")

    flag = fetch_flag_with_guarded_rollout(env_key)
    env = flag.get("environments", {}).get(env_key, {})

    if not env.get("on"):
        return {
            "on": False,
            "rolloutType": "off",
            "guardedStatus": None,
            "greenPercent": 0.0,
            "stage": 0,
            "stageTarget": 0,
            "source": "api",
        }

    fallthrough = env.get("fallthrough", {})
    guarded = env.get("guardedRollout")
    stage_targets = ROLLOUT_PERCENTAGES
    config = fallthrough.get("guardedRolloutConfig")
    if isinstance(config, dict):
        stage_targets = _stage_targets_from_config(config)

    if isinstance(guarded, dict):
        status = str(guarded.get("status", "monitoring"))
        green_percent = _green_percent_from_guarded_rollout(guarded)
        if green_percent is None:
            green_percent = _green_percent_from_fallthrough(flag, fallthrough)
        stage, target = (
            match_rollout_stage(green_percent, stage_targets)
            if green_percent is not None
            else (None, None)
        )
        return {
            "on": True,
            "rolloutType": "guarded",
            "guardedStatus": status,
            "greenPercent": green_percent,
            "stage": stage,
            "stageTarget": target,
            "source": "api",
        }

    if isinstance(config, dict):
        green_percent = _green_percent_from_fallthrough(flag, fallthrough)
        stage, target = (
            match_rollout_stage(green_percent, stage_targets)
            if green_percent is not None
            else (None, None)
        )
        return {
            "on": True,
            "rolloutType": "guarded-configured",
            "guardedStatus": None,
            "greenPercent": green_percent,
            "stage": stage,
            "stageTarget": target,
            "source": "api",
        }

    if _is_measured_rollout(fallthrough):
        rollout = fallthrough.get("rollout", {})
        green_percent = _green_percent_from_measured_rollout(flag, rollout)
        stage, target = (
            match_rollout_stage(green_percent, stage_targets)
            if green_percent is not None
            else (None, None)
        )
        return {
            "on": True,
            "rolloutType": "guarded",
            "guardedStatus": "monitoring",
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
            "guardedStatus": None,
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
        "guardedStatus": None,
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
