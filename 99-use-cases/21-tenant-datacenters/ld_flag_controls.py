"""REST controls for the Toggles tab.

The border palette turns on or off and sets the fallthrough. That fallthrough
is the palette every tenant box receives. The boolean flags turn on or off.
On serves the true variation, unless a rollout is already the default rule.
Off only turns the flag off. Enable for everybody serves the true variation
from the default rule.

REST API — patch feature flag
https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag

Feature flags — boolean variations
https://launchdarkly.com/docs/home/flags/boolean

Feature flags — multivariate variations
https://launchdarkly.com/docs/home/flags/variations
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flags import FLAG_BORDER, FLAG_FILL, FLAG_FIREWALL, FLAG_SECURITY

CONTROLLED_FLAGS: list[dict[str, str]] = [
    {
        "key": FLAG_BORDER,
        "label": "Tenant border palette",
        "summary": "One palette for every box. Off serves none. On serves the fallthrough.",
    },
    {
        "key": FLAG_FILL,
        "label": "Tenant box fill",
        "summary": "On serves Fill, unless a rollout is already the default rule. Off turns the flag off. Enable for everybody serves Fill.",
    },
    {
        "key": FLAG_SECURITY,
        "label": "Tenant security",
        "summary": "On serves Enabled, unless a rollout is already the default rule. Off turns the flag off. Enable for everybody serves Enabled.",
    },
    {
        "key": FLAG_FIREWALL,
        "label": "Tenant firewall",
        "summary": "On serves Enabled, unless a rollout is already the default rule. Off turns the flag off. Enable for everybody serves Enabled.",
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


def _variation_id(flag: dict[str, Any], wanted: Any) -> str | None:
    for variation in flag.get("variations") or []:
        if variation.get("value") == wanted:
            vid = variation.get("_id") or variation.get("id")
            if isinstance(vid, str) and vid:
                return vid
    return None


def _at(variations: list[Any], index: Any) -> dict[str, Any] | None:
    if isinstance(index, int) and 0 <= index < len(variations):
        variation = variations[index]
        return variation if isinstance(variation, dict) else None
    return None


def _label(variation: dict[str, Any] | None, fallback: str) -> str:
    if not variation:
        return fallback
    name = variation.get("name")
    if isinstance(name, str) and name:
        return name
    value = variation.get("value")
    return str(value) if value is not None else fallback


def _rollout(env: dict[str, Any]) -> bool:
    """True when the default rule is a rollout, including a progressive rollout."""
    fallthrough = env.get("fallthrough") or {}
    if isinstance(fallthrough.get("rollout"), dict):
        return True
    return isinstance(fallthrough.get("progressiveRolloutConfig"), dict)


def _summarize(flag: dict[str, Any], environment_key: str, meta: dict[str, str]) -> dict[str, Any]:
    env = (flag.get("environments") or {}).get(environment_key) or {}
    on = bool(env.get("on"))
    variations = flag.get("variations") or []
    boolean = any(isinstance(variation.get("value"), bool) for variation in variations)
    off_variation = _at(variations, env.get("offVariation"))
    fallthrough = env.get("fallthrough") or {}
    fall_variation = _at(variations, fallthrough.get("variation"))
    rollout = _rollout(env)
    off_value = off_variation.get("value") if off_variation else None
    fall_value = fall_variation.get("value") if fall_variation else None
    off_label = _label(off_variation, "off")
    fall_label = "rollout" if rollout and fall_variation is None else _label(fall_variation, "fallthrough")
    if boolean:
        if not on:
            hint = "Off. Rules and the default rule stay as they are."
        elif rollout:
            hint = "On. A rollout is the default rule, so turning the flag on left it in place."
        else:
            hint = f"On. The default rule serves {fall_label}."
        options: list[dict[str, str]] = []
        token = "true" if fall_value is True else "false" if fall_value is False else None
    else:
        options = [
            {
                "token": str(variation.get("value")),
                "label": variation.get("name") or str(variation.get("value")),
            }
            for variation in variations
            if isinstance(variation.get("value"), str)
        ]
        token = str(fall_value) if fall_value is not None else None
        if on:
            hint = f"On. Every box uses the fallthrough ({fall_value})."
        else:
            hint = f"Off. Every box uses the off variation ({off_value})."
    return {
        "key": flag.get("key") or meta["key"],
        "label": meta["label"],
        "summary": meta["summary"],
        "on": on,
        "variationKind": "boolean" if boolean else "string",
        "rollout": rollout,
        "fallthroughOptions": options,
        "fallthroughToken": token,
        "servedWhenOff": off_label if boolean else off_value,
        "servedWhenOnFallthrough": fall_label if boolean else fall_value,
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


def _instructions(
    flag: dict[str, Any],
    env: dict[str, Any],
    *,
    turn_on: bool | None,
    fallthrough: str | None,
    everybody: bool,
) -> list[dict[str, Any]]:
    """Build the semantic patch. Off never touches the default rule."""
    instructions: list[dict[str, Any]] = []
    boolean = any(isinstance(variation.get("value"), bool) for variation in flag.get("variations") or [])
    if everybody or (turn_on is True and boolean and not _rollout(env)):
        true_id = _variation_id(flag, True)
        if not true_id:
            raise ValueError(f"{flag.get('key')} has no true variation")
        instructions.append({"kind": "turnFlagOn"})
        instructions.append(
            {"kind": "updateFallthroughVariationOrRollout", "variationId": true_id}
        )
        return instructions
    if turn_on is True:
        instructions.append({"kind": "turnFlagOn"})
    elif turn_on is False:
        instructions.append({"kind": "turnFlagOff"})
    if fallthrough and not boolean:
        variation_id = _variation_id(flag, fallthrough)
        if not variation_id:
            raise ValueError(f"No variation matching fallthrough={fallthrough!r}")
        instructions.append(
            {"kind": "updateFallthroughVariationOrRollout", "variationId": variation_id}
        )
    return instructions


def apply_flag_control(
    flag_key: str,
    *,
    turn_on: bool | None = None,
    fallthrough: str | None = None,
    everybody: bool = False,
) -> dict[str, Any]:
    """Turn a toggle flag on or off, and optionally serve its true variation.

    LaunchDarkly: turnFlagOn / turnFlagOff / updateFallthroughVariationOrRollout
    https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
    """
    if flag_key not in _ALLOWED_KEYS:
        raise ValueError(f"Flag key not allowed for controls: {flag_key}")
    if turn_on is None and not fallthrough and not everybody:
        raise ValueError('Provide "on", "fallthrough", and/or "everybody"')

    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Flag controls need " + ", ".join(cfg["missing"]) + ".")
    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flag = _request("GET", f"/flags/{project}/{flag_key}?{query}")
    env = (flag.get("environments") or {}).get(environment) or {}
    instructions = _instructions(
        flag,
        env,
        turn_on=turn_on,
        fallthrough=fallthrough,
        everybody=everybody,
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
