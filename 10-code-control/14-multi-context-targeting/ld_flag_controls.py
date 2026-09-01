"""REST helpers for the 14 multi-context lab's boolean partner-badge flag.

Controls change only on/off and fallthrough. The two AND targeting rules are
provisioned by rest/create-flags.sh.
https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from partner import FLAG_PARTNER_BADGE

LD_API_HOST = os.environ.get("LD_API_HOST") or "https://app.launchdarkly.com"
LD_API_VERSION = os.environ.get("LD_API_VERSION") or "20240415"


def api_config() -> dict[str, Any]:
    """Report whether REST controls are configured without exposing secrets."""
    values = {
        "LD_API_ACCESS_TOKEN": (os.environ.get("LD_API_ACCESS_TOKEN") or "").strip(),
        "LD_PROJECT_KEY": (os.environ.get("LD_PROJECT_KEY") or "").strip(),
        "LD_ENVIRONMENT_KEY": (os.environ.get("LD_ENVIRONMENT_KEY") or "").strip(),
    }
    missing = [key for key, value in values.items() if not value]
    return {
        "configured": not missing,
        "missing": missing,
        "projectKey": values["LD_PROJECT_KEY"] or None,
        "environmentKey": values["LD_ENVIRONMENT_KEY"] or None,
        "apiHost": LD_API_HOST,
    }


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Flag controls need " + ", ".join(cfg["missing"]))
    url = f"{LD_API_HOST.rstrip('/')}/api/v2{path}"
    headers = {
        "Authorization": (os.environ.get("LD_API_ACCESS_TOKEN") or "").strip(),
        "LD-API-Version": LD_API_VERSION,
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json; domain-model=launchdarkly.semanticpatch"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        try:
            message = json.loads(detail).get("message") or detail
        except json.JSONDecodeError:
            message = detail or str(exc)
        raise RuntimeError(f"LaunchDarkly API {exc.code}: {message}") from exc


def _variation_value(flag: dict[str, Any], index: object) -> Any:
    variations = flag.get("variations") or []
    return variations[index].get("value") if isinstance(index, int) and index < len(variations) else None


def _variation_id(flag: dict[str, Any], value: object) -> str | None:
    for variation in flag.get("variations") or []:
        if variation.get("value") == value:
            return variation.get("_id") or variation.get("id")
    return None


def _summarize(flag: dict[str, Any], environment: str) -> dict[str, Any]:
    env = (flag.get("environments") or {}).get(environment) or {}
    off_index = env.get("offVariation")
    fall_index = (env.get("fallthrough") or {}).get("variation")
    options = [
        {
            "token": variation.get("value") if not isinstance(variation.get("value"), bool)
            else ("true" if variation.get("value") else "false"),
            "label": variation.get("name") or str(variation.get("value")),
            "value": variation.get("value"),
        }
        for variation in flag.get("variations") or []
    ]
    # Map boolean fallthrough tokens for the <select>
    fall_token = _variation_value(flag, fall_index)
    if isinstance(fall_token, bool):
        fall_token = "true" if fall_token else "false"
    return {
        "key": FLAG_PARTNER_BADGE,
        "name": flag.get("name") or "Show partner org badge",
        "label": "Show: partner org badge",
        "summary": "Boolean true only for alice+acme and bob+globex (provisioned AND rules).",
        "on": bool(env.get("on")),
        "variationKind": "boolean",
        "fallthroughOptions": options,
        "fallthroughToken": fall_token,
        "servedWhenOff": _variation_value(flag, off_index),
        "servedWhenOnFallthrough": _variation_value(flag, fall_index),
        "ruleCount": len(env.get("rules") or []),
        "targetingHint": (
            f"{len(env.get('rules') or [])} provisioned multi-context rules remain unchanged; "
            "this lab controls only flag state and fallthrough."
        ),
    }


def list_flag_controls() -> dict[str, Any]:
    """Fetch status for the partner-badge flag."""
    cfg = api_config()
    if not cfg["configured"]:
        return {
            **cfg,
            "flags": [{
                "key": FLAG_PARTNER_BADGE,
                "label": "Show: partner org badge",
                "summary": "Boolean targeted by user+organization multi-context rules.",
                "on": None,
                "targetingHint": "Set missing environment variables to enable controls.",
            }],
        }
    project, environment = cfg["projectKey"], cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flag = _request("GET", f"/flags/{project}/{FLAG_PARTNER_BADGE}?{query}")
    return {**cfg, "flags": [_summarize(flag, environment)], "errors": []}


def apply_flag_control(
    flag_key: str, *, turn_on: bool | None = None, fallthrough: object | None = None
) -> dict[str, Any]:
    """Apply on/off and fallthrough semantic patches without editing rules."""
    if flag_key != FLAG_PARTNER_BADGE:
        raise ValueError(f"Flag key not allowed for controls: {flag_key}")
    if turn_on is None and fallthrough is None:
        raise ValueError('Provide "on" and/or "fallthrough"')
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Flag controls need " + ", ".join(cfg["missing"]))
    project, environment = cfg["projectKey"], cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flag = _request("GET", f"/flags/{project}/{flag_key}?{query}")
    instructions: list[dict[str, Any]] = []
    if turn_on is not None:
        instructions.append({"kind": "turnFlagOn" if turn_on else "turnFlagOff"})
    if fallthrough is not None:
        wanted: object = fallthrough
        if wanted in ("true", "false"):
            wanted = wanted == "true"
        variation_id = _variation_id(flag, wanted)
        if not variation_id:
            raise ValueError(f"No variation matching fallthrough={fallthrough!r}")
        instructions.append({
            "kind": "updateFallthroughVariationOrRollout",
            "variationId": variation_id,
        })
    _request("PATCH", f"/flags/{project}/{flag_key}", {
        "environmentKey": environment,
        "comment": "14-multi-context-targeting UI: on/off or fallthrough",
        "instructions": instructions,
    })
    updated = _request("GET", f"/flags/{project}/{flag_key}?{query}")
    return {
        "ok": True,
        "action": "+".join(item["kind"] for item in instructions),
        "instructions": [item["kind"] for item in instructions],
        "projectKey": project,
        "environmentKey": environment,
        "flag": _summarize(updated, environment),
    }
