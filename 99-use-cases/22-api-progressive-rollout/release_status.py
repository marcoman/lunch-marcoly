"""Read and start the progressive environment release for this example.

The page polls the list. Start progressive release on the Release tab
POSTs the same body as rest/start-progressive-release.sh.

LaunchDarkly: environment releases — kind progressive
https://launchdarkly.com/docs/api/environment-releases
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from highlight_eval import FLAG_HIGHLIGHT

# Allocations on a release step are thousandths of a percent: 10000 is 10%.
ALLOCATION_SCALE = 1000
# Share of user contexts that receive green, held for STAGE_SECONDS each.
ROLLOUT_PERCENTAGES = (10, 20, 40, 60, 100)
STAGE_SECONDS = int(os.environ.get("STAGE_SECONDS", "60"))
RANDOMIZATION_UNIT = "user"
FLAG_API_VERSION = os.environ.get("LD_API_VERSION", "20240415")


def schedule() -> list[dict[str, int]]:
    """The percentage steps this example starts. Each entry is one hold."""
    return [
        {"percent": percent, "durationSeconds": STAGE_SECONDS}
        for percent in ROLLOUT_PERCENTAGES
    ]


def api_config() -> dict[str, str]:
    return {
        "host": os.environ.get("LD_API_HOST", "https://app.launchdarkly.com").rstrip("/"),
        "token": os.environ.get("LD_API_ACCESS_TOKEN", ""),
        "project": os.environ.get("LD_PROJECT_KEY", ""),
        "environment": os.environ.get("LD_ENVIRONMENT_KEY", ""),
    }


def targeting_url() -> str | None:
    cfg = api_config()
    if not cfg["project"] or not cfg["environment"]:
        return None
    query = urllib.parse.urlencode(
        {"env": cfg["environment"], "selected-env": cfg["environment"]}
    )
    return (
        f"{cfg['host']}/projects/{cfg['project']}/flags/{FLAG_HIGHLIGHT}/targeting?{query}"
    )


def _request(
    method: str,
    path: str,
    body: dict | None = None,
    version: str = "beta",
    content_type: str = "application/json",
) -> tuple[int, dict | list | str]:
    cfg = api_config()
    data = None if body is None else json.dumps(body).encode()
    headers = {
        "Authorization": cfg["token"],
        "LD-API-Version": version,
    }
    if data is not None:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(cfg["host"] + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw[:240]
        return exc.code, payload
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return 0, {"message": f"Could not reach LaunchDarkly: {exc.reason if hasattr(exc, 'reason') else exc}"}


def _get(path: str) -> tuple[int, dict | list | str]:
    return _request("GET", path)


def _step_view(step: dict) -> dict[str, object]:
    allocation = step.get("allocation")
    percent = None
    if isinstance(allocation, (int, float)):
        percent = allocation / ALLOCATION_SCALE
    duration = step.get("durationMillis")
    seconds = None
    if isinstance(duration, (int, float)):
        seconds = int(duration) // 1000
    return {"percent": percent, "durationSeconds": seconds}


def summarize_release(item: dict) -> dict[str, object]:
    """Turn one release payload into the fields the drawer shows."""
    phases = item.get("phases") or []
    phase = phases[0] if phases else {}
    steps = [_step_view(step) for step in (phase.get("steps") or [])]
    index = phase.get("currentStepIndex")
    current = None
    if isinstance(index, int) and 0 <= index < len(steps):
        current = steps[index]
    return {
        "configured": True,
        "flagKey": FLAG_HIGHLIGHT,
        "kind": item.get("kind"),
        "status": item.get("status"),
        "statusReason": item.get("statusReason"),
        "randomizationUnit": item.get("randomizationUnit"),
        "metricCount": len(item.get("metrics") or []),
        "hasRule": bool(phase.get("ruleId")),
        "stepIndex": index,
        "stepCount": len(steps),
        "currentPercent": None if current is None else current.get("percent"),
        "steps": steps,
        "active": item.get("endedAt") is None and item.get("status") not in {"completed", "reverted"},
    }


def latest_progressive_release() -> dict[str, object]:
    """GET the newest progressive release. An empty history is a valid result.

    LaunchDarkly: environment releases, filter kind equals progressive.
    Header LD-API-Version: beta.
    https://launchdarkly.com/docs/api/environment-releases-beta/list-environment-releases
    """
    cfg = api_config()
    if not cfg["token"] or not cfg["project"] or not cfg["environment"]:
        return {
            "configured": False,
            "flagKey": FLAG_HIGHLIGHT,
            "detail": "Set LD_API_ACCESS_TOKEN, LD_PROJECT_KEY, and LD_ENVIRONMENT_KEY, then restart.",
        }
    query = urllib.parse.urlencode(
        {"queryfilter": "kind:equals:progressive", "limit": "1"}
    )
    path = (
        f"/api/v2/projects/{cfg['project']}/flags/{FLAG_HIGHLIGHT}"
        f"/environments/{cfg['environment']}/releases?{query}"
    )
    status, payload = _get(path)
    if status != 200 or not isinstance(payload, dict):
        message = payload.get("message") if isinstance(payload, dict) else str(payload)
        return {
            "configured": True,
            "flagKey": FLAG_HIGHLIGHT,
            "error": True,
            "http": status,
            "detail": message,
        }
    items = payload.get("items") or []
    if not items:
        summary = {
            "configured": True,
            "flagKey": FLAG_HIGHLIGHT,
            "status": "none",
            "metricCount": 0,
            "steps": [],
            "detail": "No progressive release on this flag yet.",
        }
    else:
        summary = summarize_release(items[0])
        summary["totalCount"] = payload.get("totalCount")
    summary["flagOn"] = flag_is_on()
    if summary["flagOn"] is False:
        summary["active"] = False
    return summary


def _missing_config() -> dict[str, object] | None:
    cfg = api_config()
    if cfg["token"] and cfg["project"] and cfg["environment"]:
        return None
    return {
        "configured": False,
        "flagKey": FLAG_HIGHLIGHT,
        "detail": "Set LD_API_ACCESS_TOKEN, LD_PROJECT_KEY, and LD_ENVIRONMENT_KEY, then restart.",
    }


def _api_error(status: int, payload: dict | list | str) -> dict[str, object]:
    message = payload.get("message") if isinstance(payload, dict) else str(payload)
    code = payload.get("code") if isinstance(payload, dict) else None
    detail = message or "LaunchDarkly rejected the request."
    if code == "health_checks_failed":
        detail = f"{detail} Log in on the grid once so the flag has a user evaluation, then start again."
    return {
        "configured": True,
        "flagKey": FLAG_HIGHLIGHT,
        "error": True,
        "http": status,
        "code": code,
        "detail": detail,
    }


def start_body(original_variation_id: str, target_variation_id: str) -> dict[str, object]:
    """Build the progressive start body. No metrics, so the kind is progressive.

    LaunchDarkly: start an environment release
    https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release
    """
    duration_ms = STAGE_SECONDS * 1000
    return {
        "originalVariationId": original_variation_id,
        "targetVariationId": target_variation_id,
        "randomizationUnit": RANDOMIZATION_UNIT,
        "cleanupBehavior": "remove_rules_and_update_default_rule",
        "comment": "22-api-progressive-rollout: start progressive release",
        "phases": [
            {
                "description": "All users",
                "clauses": [
                    {
                        "contextKind": RANDOMIZATION_UNIT,
                        "attribute": "kind",
                        "op": "in",
                        "values": [RANDOMIZATION_UNIT],
                    }
                ],
                "steps": [
                    {"allocation": percent * ALLOCATION_SCALE, "durationMillis": duration_ms}
                    for percent in ROLLOUT_PERCENTAGES
                ],
            }
        ],
    }


def start_progressive_release() -> dict[str, object]:
    """Turn the flag on at none, then POST the progressive release.

    LaunchDarkly: start an environment release. Header LD-API-Version: beta.
    https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release
    """
    missing = _missing_config()
    if missing is not None:
        return missing
    cfg = api_config()
    flag_path = f"/api/v2/flags/{cfg['project']}/{FLAG_HIGHLIGHT}"
    status, flag = _request("GET", flag_path, version=FLAG_API_VERSION)
    if status == 404:
        return {
            "configured": True,
            "flagKey": FLAG_HIGHLIGHT,
            "error": True,
            "http": status,
            "detail": "Flag not found. Run rest/create-flag.sh, then start again.",
        }
    if status != 200 or not isinstance(flag, dict):
        return _api_error(status, flag)

    def variation_id(value: str) -> str | None:
        for item in flag.get("variations") or []:
            if item.get("value") == value and item.get("_id"):
                return str(item["_id"])
        return None

    none_id = variation_id("none")
    green_id = variation_id("green")
    if not none_id or not green_id:
        return {
            "configured": True,
            "flagKey": FLAG_HIGHLIGHT,
            "error": True,
            "detail": "The flag is missing the none or green variation.",
        }

    patch_status, patched = _request(
        "PATCH",
        flag_path,
        {
            "environmentKey": cfg["environment"],
            "comment": "22-api-progressive-rollout: on, default rule stays none",
            "instructions": [
                {"kind": "turnFlagOn"},
                {"kind": "updateFallthroughVariationOrRollout", "variationId": none_id},
            ],
        },
        version=FLAG_API_VERSION,
        content_type="application/json; domain-model=launchdarkly.semanticpatch",
    )
    if patch_status >= 400:
        return _api_error(patch_status, patched)

    release_path = (
        f"/api/v2/projects/{cfg['project']}/flags/{FLAG_HIGHLIGHT}"
        f"/environments/{cfg['environment']}/releases"
    )
    start_status, started = _request("POST", release_path, start_body(none_id, green_id))
    if start_status not in {200, 201} or not isinstance(started, dict) or "phases" not in started:
        return _api_error(start_status, started)
    summary = summarize_release(started)
    summary["started"] = True
    return summary


def _releases_path() -> str:
    cfg = api_config()
    return (
        f"/api/v2/projects/{cfg['project']}/flags/{FLAG_HIGHLIGHT}"
        f"/environments/{cfg['environment']}/releases"
    )


def stop_progressive_release() -> dict[str, object]:
    """Roll the active release back to none and remove the phase rule.

    LaunchDarkly: stop an environment release
    https://launchdarkly.com/docs/api/environment-releases-beta/stop-an-environment-release
    """
    missing = _missing_config()
    if missing is not None:
        return missing
    query = urllib.parse.urlencode({"queryfilter": "kind:equals:progressive", "limit": "5"})
    status, payload = _get(f"{_releases_path()}?{query}")
    if status != 200 or not isinstance(payload, dict):
        return _api_error(status, payload)
    active = next(
        (
            item
            for item in payload.get("items") or []
            if item.get("endedAt") is None and item.get("status") not in {"completed", "reverted"}
        ),
        None,
    )
    release_id = active.get("id") if isinstance(active, dict) else None
    if not release_id:
        return {
            "configured": True,
            "flagKey": FLAG_HIGHLIGHT,
            "error": True,
            "code": "no_active_release",
            "detail": "No active progressive release to stop.",
        }
    stop_status, stopped = _request(
        "PUT",
        f"{_releases_path()}/{release_id}/stop",
        {
            "resolution": "roll_back_all_phases_and_remove_pending_phases",
            "comment": "22-api-progressive-rollout: stop progressive release",
        },
    )
    if stop_status not in {200, 201} or not isinstance(stopped, dict):
        return _api_error(stop_status, stopped)
    summary = summarize_release(stopped)
    summary["stopped"] = True
    summary["flagOn"] = flag_is_on()
    return summary


def flag_is_on() -> bool | None:
    """Read whether the highlight flag is on in this environment."""
    cfg = api_config()
    if not cfg["token"] or not cfg["project"] or not cfg["environment"]:
        return None
    query = urllib.parse.urlencode({"env": cfg["environment"]})
    status, flag = _request(
        "GET",
        f"/api/v2/flags/{cfg['project']}/{FLAG_HIGHLIGHT}?{query}",
        version=FLAG_API_VERSION,
    )
    if status != 200 or not isinstance(flag, dict):
        return None
    environment = (flag.get("environments") or {}).get(cfg["environment"]) or {}
    return bool(environment.get("on"))


def reset_demo() -> dict[str, object]:
    """Turn the highlight flag off. Stop a running release first.

    LaunchDarkly: turn a feature flag off
    https://launchdarkly.com/docs/api/feature-flags/update-feature-flag
    """
    missing = _missing_config()
    if missing is not None:
        return missing
    stopped = stop_progressive_release()
    if stopped.get("error") and stopped.get("code") != "no_active_release":
        return stopped
    cfg = api_config()
    status, payload = _request(
        "PATCH",
        f"/api/v2/flags/{cfg['project']}/{FLAG_HIGHLIGHT}",
        {
            "environmentKey": cfg["environment"],
            "comment": "22-api-progressive-rollout: reset, flag off",
            "instructions": [{"kind": "turnFlagOff"}],
        },
        version=FLAG_API_VERSION,
        content_type="application/json; domain-model=launchdarkly.semanticpatch",
    )
    if status >= 400:
        return _api_error(status, payload)
    summary = latest_progressive_release()
    summary["reset"] = True
    summary["flagOn"] = False
    summary["active"] = False
    return summary
