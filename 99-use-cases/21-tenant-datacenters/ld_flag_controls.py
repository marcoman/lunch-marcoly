"""REST controls for the tenant border palette.

The in-app control turns the flag on or off and sets the fallthrough.
That fallthrough is the palette every tenant box receives.

REST API — patch feature flag
https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flags import FLAG_BORDER

CONTROLLED_FLAGS: list[dict[str, str]] = [
    {
        "key": FLAG_BORDER,
        "label": "Tenant border palette",
        "summary": "One palette for every box. Off serves none. On serves the fallthrough.",
    },
]

_ALLOWED_KEYS = frozenset(item["key"] for item in CONTROLLED_FLAGS)
LD_API_HOST = os.environ.get("LD_API_HOST") or "https://app.launchdarkly.com"
LD_API_VERSION = os.environ.get("LD_API_VERSION") or "20240415"


def api_config() -> dict[str, Any]:
    """Return whether the control can call the REST API. No secrets."""
    token = (os.environ.get("LD_API_ACCESS_TOKEN") or "").strip()
    project = (os.environ.get("LD_PROJECT_KEY") or "").strip()
    environment = (os.environ.get("LD_ENVIRONMENT_KEY") or "").strip()
    missing: list[str] = []
    if not token:
        missing.append("LD_API_ACCESS_TOKEN")
    if not project:
        missing.append("LD_PROJECT_KEY")
    if not environment:
        missing.append("LD_ENVIRONMENT_KEY")
    return {
        "configured": not missing,
        "missing": missing,
        "projectKey": project or None,
        "environmentKey": environment or None,
    }


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Flag controls need " + ", ".join(cfg["missing"]) + ".")
    token = (os.environ.get("LD_API_ACCESS_TOKEN") or "").strip()
    url = f"{LD_API_HOST.rstrip('/')}/api/v2{path}"
    data = None
    headers = {
        "Authorization": token,
        "LD-API-Version": LD_API_VERSION,
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = (
            "application/json; domain-model=launchdarkly.semanticpatch"
            if method == "PATCH"
            else "application/json"
        )
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(detail).get("message") or detail
        except json.JSONDecodeError:
            message = detail or str(exc)
        raise RuntimeError(f"LaunchDarkly API {exc.code}: {message}") from exc


def _variation_id(flag: dict[str, Any], wanted: str) -> str | None:
    for variation in flag.get("variations") or []:
        if variation.get("value") == wanted:
            vid = variation.get("_id") or variation.get("id")
            if isinstance(vid, str) and vid:
                return vid
    return None


def _summarize(flag: dict[str, Any], environment_key: str, meta: dict[str, str]) -> dict[str, Any]:
    env = (flag.get("environments") or {}).get(environment_key) or {}
    on = bool(env.get("on"))
    variations = flag.get("variations") or []
    off_idx = env.get("offVariation")
    fall_idx = (env.get("fallthrough") or {}).get("variation")
    off_value = variations[off_idx].get("value") if isinstance(off_idx, int) and off_idx < len(variations) else None
    fall_value = variations[fall_idx].get("value") if isinstance(fall_idx, int) and fall_idx < len(variations) else None
    options = [
        {
            "token": str(variation.get("value")),
            "label": variation.get("name") or str(variation.get("value")),
        }
        for variation in variations
        if isinstance(variation.get("value"), str)
    ]
    if on:
        hint = f"On. Every box uses the fallthrough ({fall_value})."
    else:
        hint = f"Off. Every box uses the off variation ({off_value})."
    return {
        "key": flag.get("key") or meta["key"],
        "label": meta["label"],
        "summary": meta["summary"],
        "on": on,
        "variationKind": "string",
        "fallthroughOptions": options,
        "fallthroughToken": str(fall_value) if fall_value is not None else None,
        "servedWhenOff": off_value,
        "servedWhenOnFallthrough": fall_value,
        "targetingHint": hint,
    }


def list_flag_controls() -> dict[str, Any]:
    """Read on/off and the fallthrough palette.

    LaunchDarkly: get feature flag
    https://launchdarkly.com/docs/api/feature-flags/get-feature-flag
    """
    cfg = api_config()
    if not cfg["configured"]:
        return {
            **cfg,
            "flags": [
                {
                    "key": item["key"],
                    "label": item["label"],
                    "summary": item["summary"],
                    "on": None,
                    "targetingHint": "Set the missing environment variables to enable the control.",
                }
                for item in CONTROLLED_FLAGS
            ],
        }

    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flags_out: list[dict[str, Any]] = []
    for meta in CONTROLLED_FLAGS:
        try:
            flag = _request("GET", f"/flags/{project}/{meta['key']}?{query}")
            flags_out.append(_summarize(flag, environment, meta))
        except Exception as exc:  # noqa: BLE001
            flags_out.append(
                {
                    "key": meta["key"],
                    "label": meta["label"],
                    "summary": meta["summary"],
                    "on": None,
                    "targetingHint": str(exc),
                    "error": str(exc),
                }
            )
    return {**cfg, "flags": flags_out}


def apply_flag_control(
    flag_key: str,
    *,
    turn_on: bool | None = None,
    fallthrough: str | None = None,
) -> dict[str, Any]:
    """Turn the border flag on or off, and set the palette everyone receives.

    LaunchDarkly: turnFlagOn / turnFlagOff / updateFallthroughVariationOrRollout
    https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
    """
    if flag_key not in _ALLOWED_KEYS:
        raise ValueError(f"Flag key not allowed for controls: {flag_key}")
    if turn_on is None and not fallthrough:
        raise ValueError('Provide "on" and/or "fallthrough"')

    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Flag controls need " + ", ".join(cfg["missing"]) + ".")
    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flag = _request("GET", f"/flags/{project}/{flag_key}?{query}")

    instructions: list[dict[str, Any]] = []
    if turn_on is True:
        instructions.append({"kind": "turnFlagOn"})
    elif turn_on is False:
        instructions.append({"kind": "turnFlagOff"})
    if fallthrough:
        variation_id = _variation_id(flag, fallthrough)
        if not variation_id:
            raise ValueError(f"No variation matching fallthrough={fallthrough!r}")
        instructions.append(
            {"kind": "updateFallthroughVariationOrRollout", "variationId": variation_id}
        )

    _request(
        "PATCH",
        f"/flags/{project}/{flag_key}",
        {
            "environmentKey": environment,
            "comment": "21-tenant-datacenters control",
            "instructions": instructions,
        },
    )
    flag = _request("GET", f"/flags/{project}/{flag_key}?{query}")
    meta = next(item for item in CONTROLLED_FLAGS if item["key"] == flag_key)
    return {
        "ok": True,
        "projectKey": project,
        "environmentKey": environment,
        "instructions": [item["kind"] for item in instructions],
        "flag": _summarize(flag, environment, meta),
    }
