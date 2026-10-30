"""Read and start the guarded environment release for this example.

Including metrics makes the release kind guarded. The page polls the list.
Start guarded release POSTs the beta releases endpoint.

LaunchDarkly: environment releases — kind guarded
https://launchdarkly.com/docs/api/environment-releases
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from highlight_eval import FLAG_HIGHLIGHT
from metrics import METRIC_DEFINITIONS, create_body, metric_views

# Allocations are thousandths of a percent. Guarded releases stop at 50000 (50%).
ALLOCATION_SCALE = 1000
# First two stages are long enough to cross the latency guardrail. The rest finish faster.
ROLLOUT_STEPS = (
    {"percent": 10, "durationSeconds": 120},
    {"percent": 20, "durationSeconds": 120},
    {"percent": 30, "durationSeconds": 60},
    {"percent": 50, "durationSeconds": 60},
)
RANDOMIZATION_UNIT = "user"
FLAG_API_VERSION = os.environ.get("LD_API_VERSION", "20240415")
# A quiet error-rate metric has no events. These checks would block Start.
# Flag-evaluation checks still run, so log in once before starting.
METRIC_HEALTH_CHECKS = ("metric_events_any", "metric_events_with_context")


def schedule() -> list[dict[str, int]]:
    """The percentage steps this example starts. Each entry is one hold."""
    return [dict(step) for step in ROLLOUT_STEPS]


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
    body: dict | list | None = None,
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
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw[:240]
        return exc.code, payload
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        reason = exc.reason if hasattr(exc, "reason") else exc
        return 0, {"message": f"Could not reach LaunchDarkly: {reason}"}


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


def _regressed_metrics(phase: dict) -> list[str]:
    statuses = phase.get("metricStatuses") or {}
    if not isinstance(statuses, dict):
        return []
    return [key for key, value in statuses.items() if value == "regressed"]


def headline(item: dict[str, object]) -> str:
    """One line for the Release tab. No step percentage."""
    if item.get("flagOn") is False:
        return "Flag is off. Every context receives none."
    status = item.get("status")
    if status in {None, "none"}:
        return str(item.get("detail") or "No guarded release yet.")
    reason = item.get("statusReason")
    regressed = item.get("regressedMetrics") or []
    names = ", ".join(regressed) if isinstance(regressed, list) else ""
    rolled_back = status == "reverted" or item.get("stopped") is True
    if rolled_back and (reason == "reverted_regression_detected" or names):
        which = names or "A guardrail"
        return f"Rolled back to none. {which} regressed."
    if rolled_back:
        return "Rolled back to none."
    if status == "waiting" and reason == "waiting_regression_detected":
        which = names or "A guardrail"
        return f"Paused. {which} regressed."
    if status == "completed":
        return "Completed."
    if status == "in_progress":
        return "Monitoring."
    return "Monitoring." if item.get("active") else str(status or "Waiting.")


def summarize_release(item: dict) -> dict[str, object]:
    """Turn one release payload into the status line the page shows."""
    phases = item.get("phases") or []
    phase = phases[0] if phases else {}
    steps = [_step_view(step) for step in (phase.get("steps") or [])]
    summary = {
        "configured": True,
        "flagKey": FLAG_HIGHLIGHT,
        "kind": item.get("kind"),
        "status": item.get("status"),
        "statusReason": item.get("statusReason"),
        "metricCount": len(item.get("metrics") or []),
        "regressedMetrics": _regressed_metrics(phase),
        "stepIndex": phase.get("currentStepIndex"),
        "stepCount": len(steps),
        "steps": steps,
        "active": item.get("endedAt") is None and item.get("status") not in {"completed", "reverted"},
    }
    summary["headline"] = headline(summary)
    return summary


def latest_guarded_release() -> dict[str, object]:
    """GET the newest guarded release. An empty history is a valid result.

    LaunchDarkly: environment releases, filter kind equals guarded.
    Header LD-API-Version: beta.
    https://launchdarkly.com/docs/api/environment-releases-beta/list-environment-releases
    """
    missing = _missing_config()
    if missing is not None:
        return missing
    cfg = api_config()
    query = urllib.parse.urlencode({"queryfilter": "kind:equals:guarded", "limit": "1"})
    path = (
        f"/api/v2/projects/{cfg['project']}/flags/{FLAG_HIGHLIGHT}"
        f"/environments/{cfg['environment']}/releases?{query}"
    )
    status, payload = _request("GET", path)
    if status == 404:
        summary = {
            "configured": True,
            "flagKey": FLAG_HIGHLIGHT,
            "status": "none",
            "detail": "No flag yet. Start creates it.",
        }
        summary["headline"] = headline(summary)
        summary["flagOn"] = False
        return summary
    if status != 200 or not isinstance(payload, dict):
        return _api_error(status, payload)
    items = payload.get("items") or []
    if not items:
        summary = {
            "configured": True,
            "flagKey": FLAG_HIGHLIGHT,
            "status": "none",
            "metricCount": 0,
            "steps": [],
            "detail": "No guarded release on this flag yet.",
        }
    else:
        summary = summarize_release(items[0])
    summary["flagOn"] = flag_is_on()
    if summary["flagOn"] is False:
        summary["active"] = False
    summary["headline"] = headline(summary)
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
        detail = (
            f"{detail} Log in on the grid once so the flag has a user evaluation, then start again."
        )
    return {
        "configured": True,
        "flagKey": FLAG_HIGHLIGHT,
        "error": True,
        "http": status,
        "code": code,
        "detail": detail,
    }


def start_body(original_variation_id: str, target_variation_id: str) -> dict[str, object]:
    """Build the guarded start body. Metrics make the kind guarded.

    LaunchDarkly: start an environment release
    https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release
    """
    return {
        "originalVariationId": original_variation_id,
        "targetVariationId": target_variation_id,
        "randomizationUnit": RANDOMIZATION_UNIT,
        "cleanupBehavior": "remove_rules_and_update_default_rule",
        "comment": "23-api-guarded-rollout: start guarded release",
        "bypassHealthChecks": list(METRIC_HEALTH_CHECKS),
        "metrics": [
            {"metricKey": item["key"], "autoRollback": True}
            for item in METRIC_DEFINITIONS
        ],
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
                    {
                        "allocation": step["percent"] * ALLOCATION_SCALE,
                        "durationMillis": step["durationSeconds"] * 1000,
                    }
                    for step in ROLLOUT_STEPS
                ],
            }
        ],
    }


def _flag_path() -> str:
    cfg = api_config()
    return f"/api/v2/flags/{cfg['project']}/{FLAG_HIGHLIGHT}"


def _releases_path() -> str:
    cfg = api_config()
    return (
        f"/api/v2/projects/{cfg['project']}/flags/{FLAG_HIGHLIGHT}"
        f"/environments/{cfg['environment']}/releases"
    )


def _phase_rule_ids(flag: dict) -> list[str]:
    """Ids of targeting rules left behind by a stopped release."""
    environment = (flag.get("environments") or {}).get(api_config()["environment"]) or {}
    rule_ids: list[str] = []
    for rule in environment.get("rules") or []:
        rule_id = rule.get("_id") or rule.get("id")
        if isinstance(rule_id, str):
            rule_ids.append(rule_id)
    return rule_ids


def _variation_id(flag: dict, value: str) -> str | None:
    for item in flag.get("variations") or []:
        if item.get("value") == value and item.get("_id"):
            return str(item["_id"])
    return None


def ensure_flag() -> dict[str, object] | None:
    """Create the string flag when it is missing. Leave an existing flag alone.

    Variation text names the color. It does not cite a repository URL.
    """
    status, flag = _request("GET", _flag_path(), version=FLAG_API_VERSION)
    if status == 200 and isinstance(flag, dict):
        return None
    if status != 404:
        return _api_error(status, flag)
    created, payload = _request(
        "POST",
        f"/api/v2/flags/{api_config()['project']}",
        {
            "key": FLAG_HIGHLIGHT,
            "name": "API guarded grid highlight",
            "description": (
                "Guarded rollout of the grid highlight from none to green, "
                "started with the environment releases API. "
                "Latency, error rate, and movement are the guardrails."
            ),
            "temporary": False,
            "tags": [
                "grid-navigator",
                "use-case",
                "api-guarded-rollout",
                "environment-release",
                "guarded-rollout",
                "string",
            ],
            "variations": [
                {
                    "value": "none",
                    "name": "No highlight",
                    "description": "Selected cell stays dark. The release starts here.",
                },
                {
                    "value": "green",
                    "name": "Green",
                    "description": "Selected cell turns green. The release moves traffic here.",
                },
                {
                    "value": "yellow",
                    "name": "Yellow",
                    "description": "Yellow highlight. This release does not target it.",
                },
                {
                    "value": "red",
                    "name": "Red",
                    "description": "Red highlight. This release does not target it.",
                },
                {
                    "value": "blue",
                    "name": "Blue",
                    "description": "Blue highlight. This release does not target it.",
                },
                {
                    "value": "purple",
                    "name": "Purple",
                    "description": "Purple highlight. This release does not target it.",
                },
            ],
            "defaults": {"onVariation": 1, "offVariation": 0},
        },
        version=FLAG_API_VERSION,
    )
    if created not in {200, 201}:
        return _api_error(created, payload)
    return None


def ensure_metrics() -> list[str]:
    """Create any missing guardrail. Refresh a description that is still thin.

    The three keys belong to example 15 as well. Start writes the 23 wording
    so a reader opening the metric can see what this lab is doing.
    """
    warnings: list[str] = []
    project = api_config()["project"]
    for definition in METRIC_DEFINITIONS:
        key = definition["key"]
        path = f"/api/v2/metrics/{project}/{key}"
        status, existing = _request("GET", path, version=FLAG_API_VERSION)
        description = definition["description"]
        if status == 404:
            created, payload = _request(
                "POST",
                f"/api/v2/metrics/{project}",
                create_body(definition),
                version=FLAG_API_VERSION,
            )
            if created not in {200, 201}:
                message = payload.get("message") if isinstance(payload, dict) else payload
                warnings.append(f"{key}: create failed ({created}) {message}")
            continue
        if status != 200 or not isinstance(existing, dict):
            warnings.append(f"{key}: could not read the metric ({status})")
            continue
        if existing.get("description") == description:
            continue
        patched, payload = _request(
            "PATCH",
            path,
            [{"op": "replace", "path": "/description", "value": description}],
            version=FLAG_API_VERSION,
        )
        if patched >= 400:
            message = payload.get("message") if isinstance(payload, dict) else payload
            warnings.append(f"{key}: description was not updated ({patched}) {message}")
    return warnings


def start_guarded_release() -> dict[str, object]:
    """Turn the flag on at none, then POST the guarded release.

    LaunchDarkly: start an environment release. Header LD-API-Version: beta.
    https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release
    """
    missing = _missing_config()
    if missing is not None:
        return missing
    warnings = ensure_metrics()
    flag_error = ensure_flag()
    if flag_error is not None:
        return flag_error
    cfg = api_config()
    status, flag = _request("GET", _flag_path(), version=FLAG_API_VERSION)
    if status != 200 or not isinstance(flag, dict):
        return _api_error(status, flag)
    none_id = _variation_id(flag, "none")
    green_id = _variation_id(flag, "green")
    if not none_id or not green_id:
        return {
            "configured": True,
            "flagKey": FLAG_HIGHLIGHT,
            "error": True,
            "detail": "The flag is missing the none or green variation.",
        }
    patch_status, patched = _request(
        "PATCH",
        _flag_path(),
        {
            "environmentKey": cfg["environment"],
            "comment": "23-api-guarded-rollout: on, default rule stays none",
            "instructions": [
                *({"kind": "removeRule", "ruleId": rule_id} for rule_id in _phase_rule_ids(flag)),
                {"kind": "turnFlagOn"},
                {"kind": "updateFallthroughVariationOrRollout", "variationId": none_id},
            ],
        },
        version=FLAG_API_VERSION,
        content_type="application/json; domain-model=launchdarkly.semanticpatch",
    )
    if patch_status >= 400:
        return _api_error(patch_status, patched)
    start_status, started = _request("POST", _releases_path(), start_body(none_id, green_id))
    if start_status not in {200, 201} or not isinstance(started, dict) or "phases" not in started:
        return _api_error(start_status, started)
    summary = summarize_release(started)
    summary["started"] = True
    summary["flagOn"] = True
    summary["headline"] = headline(summary)
    if warnings:
        summary["metricDescriptionWarning"] = " ".join(warnings)
    return summary


def stop_guarded_release() -> dict[str, object]:
    """Roll the active release back to none.

    The phase rule stays. The next start or reset removes it.

    LaunchDarkly: stop an environment release
    https://launchdarkly.com/docs/api/environment-releases-beta/stop-an-environment-release
    """
    missing = _missing_config()
    if missing is not None:
        return missing
    query = urllib.parse.urlencode({"queryfilter": "kind:equals:guarded", "limit": "5"})
    status, payload = _request("GET", f"{_releases_path()}?{query}")
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
            "detail": "No active guarded release to stop.",
        }
    stop_status, stopped = _request(
        "PUT",
        f"{_releases_path()}/{release_id}/stop",
        {
            "resolution": "roll_back_all_phases_and_remove_pending_phases",
            "comment": "23-api-guarded-rollout: stop guarded release",
        },
    )
    if stop_status not in {200, 201} or not isinstance(stopped, dict):
        return _api_error(stop_status, stopped)
    summary = summarize_release(stopped)
    summary["stopped"] = True
    summary["flagOn"] = flag_is_on()
    summary["headline"] = headline(summary)
    return summary


def flag_is_on() -> bool | None:
    """Read whether the highlight flag is on in this environment."""
    cfg = api_config()
    if not cfg["token"] or not cfg["project"] or not cfg["environment"]:
        return None
    query = urllib.parse.urlencode({"env": cfg["environment"]})
    status, flag = _request(
        "GET",
        f"{_flag_path()}?{query}",
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
    stopped = stop_guarded_release()
    if stopped.get("error") and stopped.get("code") != "no_active_release":
        return stopped
    flag_status, flag = _request("GET", _flag_path(), version=FLAG_API_VERSION)
    instructions: list[dict[str, str]] = [{"kind": "turnFlagOff"}]
    if flag_status == 200 and isinstance(flag, dict):
        instructions = [
            {"kind": "removeRule", "ruleId": rule_id} for rule_id in _phase_rule_ids(flag)
        ] + instructions
    status, payload = _request(
        "PATCH",
        _flag_path(),
        {
            "environmentKey": api_config()["environment"],
            "comment": "23-api-guarded-rollout: reset, flag off, phase rule removed",
            "instructions": instructions,
        },
        version=FLAG_API_VERSION,
        content_type="application/json; domain-model=launchdarkly.semanticpatch",
    )
    if status >= 400:
        return _api_error(status, payload)
    summary = latest_guarded_release()
    summary["reset"] = True
    summary["flagOn"] = False
    summary["active"] = False
    summary["headline"] = "Flag is off. Every context receives none."
    return summary


def _assert_start_body() -> None:
    body = start_body("none-id", "green-id")
    steps = body["phases"][0]["steps"]
    assert [step["allocation"] for step in steps] == [10000, 20000, 30000, 50000]
    assert [step["durationMillis"] for step in steps] == [120000, 120000, 60000, 60000]
    assert [item["metricKey"] for item in body["metrics"]] == [
        "grid-nav-latency",
        "grid-highlight-error-rate",
        "grid-nav-movement",
    ]
    assert all(item["autoRollback"] is True for item in body["metrics"])
    assert body["bypassHealthChecks"] == list(METRIC_HEALTH_CHECKS)
    assert "metrics" in body
    views = metric_views()
    assert [item["role"] for item in views] == ["violation", "normal", "normal"]
    print("ok", len(views))


if __name__ == "__main__":
    _assert_start_body()
