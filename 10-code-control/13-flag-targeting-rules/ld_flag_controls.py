"""REST helpers for the 13 targeting-rules lab's single string flag.

Controls intentionally change only on/off and fallthrough. The three targeting
rules are provisioned by Terraform or ``rest/create-flags.sh``.
https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from team_style import FLAG_TEAM_DISPLAY_LABELS, FLAG_TEAM_LABEL_STYLE

CONTROLLED_FLAGS = (
    (
        FLAG_TEAM_LABEL_STYLE,
        "Configure team label style",
        "String style selected by provisioned targeting rules on public team.",
    ),
    (
        FLAG_TEAM_DISPLAY_LABELS,
        "Configure team display labels",
        "JSON words for the pill and the team switch. Team values stay red, blue, and yellow.",
    ),
)

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


def _option_token(variation: dict[str, Any]) -> object:
    """String flags use the value. JSON flags use the variation name."""
    value = variation.get("value")
    if isinstance(value, (dict, list)):
        return variation.get("name") or json.dumps(value, sort_keys=True)
    return value


def _variation_id(flag: dict[str, Any], token: object) -> str | None:
    for variation in flag.get("variations") or []:
        if _option_token(variation) == token or variation.get("value") == token:
            return variation.get("_id") or variation.get("id")
    return None


def _summarize(
    flag: dict[str, Any], environment: str, label: str, summary: str
) -> dict[str, Any]:
    env = (flag.get("environments") or {}).get(environment) or {}
    off_index = env.get("offVariation")
    fall_index = (env.get("fallthrough") or {}).get("variation")
    variations = flag.get("variations") or []
    options = [
        {
            "token": _option_token(variation),
            "label": variation.get("name") or _option_token(variation),
            "value": variation.get("value"),
        }
        for variation in variations
    ]
    fall_variation = variations[fall_index] if isinstance(fall_index, int) and fall_index < len(variations) else {}
    kind = "json" if any(isinstance(item.get("value"), (dict, list)) for item in variations) else "string"
    return {
        "key": flag.get("key"),
        "name": flag.get("name") or label,
        "label": label,
        "summary": summary,
        "on": bool(env.get("on")),
        "variationKind": kind,
        "fallthroughOptions": options,
        "fallthroughToken": _option_token(fall_variation) if fall_variation else None,
        "servedWhenOff": _variation_value(flag, off_index),
        "servedWhenOnFallthrough": _variation_value(flag, fall_index),
        "ruleCount": len(env.get("rules") or []),
        "targetingHint": (
            f"{len(env.get('rules') or [])} provisioned rules remain unchanged; "
            "this lab controls only flag state and fallthrough."
        ),
    }


def list_flag_controls() -> dict[str, Any]:
    """Fetch status and variations for the style flag and the display-label flag."""
    cfg = api_config()
    if not cfg["configured"]:
        return {
            **cfg,
            "flags": [
                {
                    "key": key,
                    "label": label,
                    "summary": summary,
                    "on": None,
                    "targetingHint": "Set missing environment variables to enable controls.",
                }
                for key, label, summary in CONTROLLED_FLAGS
            ],
        }
    project, environment = cfg["projectKey"], cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flags: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for key, label, summary in CONTROLLED_FLAGS:
        try:
            flag = _request("GET", f"/flags/{project}/{key}?{query}")
            flags.append(_summarize(flag, environment, label, summary))
        except RuntimeError as exc:
            errors.append({"key": key, "error": str(exc)})
            flags.append({
                "key": key,
                "label": label,
                "summary": summary,
                "on": None,
                "targetingHint": str(exc),
            })
    return {**cfg, "flags": flags, "errors": errors}


def apply_flag_control(
    flag_key: str, *, turn_on: bool | None = None, fallthrough: object | None = None
) -> dict[str, Any]:
    """Apply on/off and fallthrough semantic patches without editing rules."""
    allowed = {key for key, _, _ in CONTROLLED_FLAGS}
    if flag_key not in allowed:
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
        wanted = fallthrough if isinstance(fallthrough, str) else str(fallthrough)
        variation_id = _variation_id(flag, wanted)
        if not variation_id:
            raise ValueError(f"No variation matching fallthrough={wanted!r}")
        instructions.append({
            "kind": "updateFallthroughVariationOrRollout",
            "variationId": variation_id,
        })
    _request("PATCH", f"/flags/{project}/{flag_key}", {
        "environmentKey": environment,
        "comment": "13-flag-targeting-rules UI: on/off or fallthrough",
        "instructions": instructions,
    })
    updated = _request("GET", f"/flags/{project}/{flag_key}?{query}")
    return {
        "ok": True,
        "action": "+".join(item["kind"] for item in instructions),
        "instructions": [item["kind"] for item in instructions],
        "projectKey": project,
        "environmentKey": environment,
        "flag": _summarize(
            updated,
            environment,
            next(label for key, label, _ in CONTROLLED_FLAGS if key == flag_key),
            next(summary for key, _, summary in CONTROLLED_FLAGS if key == flag_key),
        ),
    }
