"""Read and reset the native progressive rollout on tenant-box-fill.

LaunchDarkly advances the steps. This lab watches the fallthrough and can
return the flag to Empty so a new rollout can be created.

Progressive rollouts — https://launchdarkly.com/docs/home/releases/progressive-rollouts
"""

from __future__ import annotations

import os
import time
import urllib.parse
from typing import Any

from flags import FLAG_FILL
from ld_flag_controls import _request, api_config

# Five one-minute steps. 100% is the state after the last minute, not a sixth step.
STAGES = (5, 10, 25, 50, 75)
FINAL_PERCENT = 100
STAGE_MS = 60_000


def flag_console_url(project: str | None, environment: str | None, flag_key: str) -> str | None:
    """Deep link to this flag. Project and environment come from the server, not the repo.

    The path is /projects/{project}/flags/{flag}?env={environment}&selected-env={environment}.
    """
    if not project or not environment or not flag_key:
        return None
    host = (
        os.environ.get("LD_APP_HOST")
        or os.environ.get("LD_API_HOST")
        or "https://app.launchdarkly.com"
    ).rstrip("/")
    project_key = urllib.parse.quote(project, safe="")
    flag = urllib.parse.quote(flag_key, safe="")
    env = urllib.parse.quote(environment, safe="")
    return f"{host}/projects/{project_key}/flags/{flag}?env={env}&selected-env={env}"


def _variation(flag: dict[str, Any], wanted: bool) -> tuple[int | None, str | None]:
    for index, variation in enumerate(flag.get("variations") or []):
        if variation.get("value") is wanted:
            vid = variation.get("_id") or variation.get("id")
            return index, vid if isinstance(vid, str) else None
    return None, None


def _fill_percent(flag: dict[str, Any], fallthrough: dict[str, Any], fill_index: int | None) -> float | None:
    if fill_index is None:
        return None
    if "variation" in fallthrough and fallthrough.get("rollout") is None:
        return 100.0 if fallthrough.get("variation") == fill_index else 0.0
    rollout = fallthrough.get("rollout")
    if not isinstance(rollout, dict):
        return None
    tracked = 0.0
    tracked_found = False
    any_weight = 0.0
    any_found = False
    for entry in rollout.get("variations") or []:
        if entry.get("variation") != fill_index:
            continue
        weight = entry.get("weight", 0)
        if not isinstance(weight, (int, float)):
            continue
        any_weight += weight / 1000.0
        any_found = True
        # A measured rollout splits a tracked slice from the rest. A progressive
        # rollout with no metric marks every bucket untracked, and that weight
        # is the step that is serving now.
        if entry.get("_untracked") is True:
            continue
        tracked += weight / 1000.0
        tracked_found = True
    if tracked_found:
        return tracked
    return any_weight if any_found else None


def _stage_for(percent: float | None) -> int | None:
    if percent is None:
        return None
    if percent >= FINAL_PERCENT:
        return len(STAGES) + 1
    for index, target in enumerate(STAGES, start=1):
        if abs(percent - target) < 0.5:
            return index
    return None


def fill_rollout_status() -> dict[str, Any]:
    """Read the current progressive-rollout step from the flag.

    LaunchDarkly: get feature flag
    https://launchdarkly.com/docs/api/feature-flags/get-feature-flag
    """
    schedule = [{"percent": percent, "seconds": STAGE_MS // 1000} for percent in STAGES]
    cfg = api_config()
    base = {
        "key": FLAG_FILL,
        "stages": schedule,
        "finalPercent": FINAL_PERCENT,
        "stageMs": STAGE_MS,
        "contextKind": "tenant",
        "flagUrl": flag_console_url(cfg.get("projectKey"), cfg.get("environmentKey"), FLAG_FILL),
    }
    if not cfg["configured"]:
        return {**base, **cfg, "status": "unconfigured", "percent": None, "stage": None}
    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flag = _request("GET", f"/flags/{project}/{FLAG_FILL}?{query}")
    env = (flag.get("environments") or {}).get(environment) or {}
    fallthrough = env.get("fallthrough") or {}
    fill_index, _fill_id = _variation(flag, True)
    percent = _fill_percent(flag, fallthrough, fill_index)
    allocation = ((fallthrough.get("rollout") or {}).get("experimentAllocation") or {}).get("type")
    configured = isinstance(fallthrough.get("progressiveRolloutConfig"), dict)
    progressive = allocation == "progressiveRollout" or configured
    on = bool(env.get("on"))
    if not on:
        percent = 0.0
    stage = _stage_for(percent) if on else None
    last_modified = env.get("lastModified")
    remaining_ms = None
    if progressive and on and isinstance(last_modified, (int, float)) and stage and stage <= len(STAGES):
        elapsed = int(time.time() * 1000) - int(last_modified)
        remaining_ms = max(0, STAGE_MS - elapsed)
    if not on:
        status = "off"
    elif progressive and percent is not None and percent >= FINAL_PERCENT:
        status = "complete"
    elif progressive and on and fallthrough.get("rollout"):
        status = "active"
    elif progressive:
        status = "ready"
    elif on:
        status = "on"
    else:
        status = "off"
    return {
        **base,
        **cfg,
        "status": status,
        "on": on,
        "percent": percent,
        "stage": stage,
        "remainingMs": remaining_ms,
        "lastModified": last_modified,
        "allocationType": allocation,
    }


def reset_fill_rollout() -> dict[str, Any]:
    """Serve Empty to everyone and turn the flag off, so a new rollout can start.

    LaunchDarkly: turnFlagOff / updateFallthroughVariationOrRollout
    https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
    """
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Flag controls need " + ", ".join(cfg["missing"]) + ".")
    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flag = _request("GET", f"/flags/{project}/{FLAG_FILL}?{query}")
    _index, empty_id = _variation(flag, False)
    if not empty_id:
        raise RuntimeError("tenant-box-fill has no Empty variation.")
    _request(
        "PATCH",
        f"/flags/{project}/{FLAG_FILL}",
        {
            "environmentKey": environment,
            "comment": "21-tenant-datacenters: reset fill rollout",
            "instructions": [
                {"kind": "updateFallthroughVariationOrRollout", "variationId": empty_id},
                {"kind": "turnFlagOff"},
            ],
        },
    )
    return fill_rollout_status()
