"""LaunchDarkly REST helpers for in-app flag controls (12-flag-variations).

Uses semantic patch turnFlagOn / turnFlagOff / updateFallthroughVariationOrRollout.
Does not invent variation definitions — only environment targeting + fallthrough.

REST API — feature flags
https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flag_variations import (
    FLAG_COUNT_LABEL,
    FLAG_LUCKY_NUMBER,
    FLAG_MAX_MOVES,
)
from host_os import FLAG_ANON_OS_EMOJI

CONTROLLED_FLAGS: list[dict[str, str]] = [
    {
        "key": FLAG_ANON_OS_EMOJI,
        "label": "Show anonymous host OS emoji",
        "summary": (
            "Boolean, evaluated with an anonymous context + private hostOs. "
            "LaunchDarkly gates visibility; the app maps host OS → emoji."
        ),
    },
    {
        "key": FLAG_COUNT_LABEL,
        "label": "Configure navigation count label",
        "summary": (
            "String variation — fallthrough chooses the header label "
            "(Count / Moves / …). Toggle on/off; pick fallthrough when on."
        ),
    },
    {
        "key": FLAG_LUCKY_NUMBER,
        "label": "Configure lucky number",
        "summary": "Number variation — fallthrough chooses Lucky Number is: N (0–5).",
    },
    {
        "key": FLAG_MAX_MOVES,
        "label": "Configure max navigation moves",
        "summary": (
            "JSON variation — fallthrough chooses {\"maxMoves\": N} for the "
            "session move cap."
        ),
    },
]

_ALLOWED_KEYS = frozenset(item["key"] for item in CONTROLLED_FLAGS)

LD_API_HOST = os.environ.get("LD_API_HOST") or "https://app.launchdarkly.com"
LD_API_VERSION = os.environ.get("LD_API_VERSION") or "20240415"


def api_config() -> dict[str, Any]:
    """Return whether write/status controls can run (no secrets)."""
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
        "apiHost": LD_API_HOST,
    }


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError(
            "Flag controls need "
            + ", ".join(cfg["missing"])
            + " in the server environment."
        )
    token = (os.environ.get("LD_API_ACCESS_TOKEN") or "").strip()
    url = f"{LD_API_HOST.rstrip('/')}/api/v2{path}"
    data = None
    headers = {
        "Authorization": token,
        "LD-API-Version": LD_API_VERSION,
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = (
            "application/json; domain-model=launchdarkly.semanticpatch"
            if method == "PATCH"
            else "application/json"
        )
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            message = parsed.get("message") or detail
        except json.JSONDecodeError:
            message = detail or str(exc)
        raise RuntimeError(f"LaunchDarkly API {exc.code}: {message}") from exc


def _variation_value(flag: dict[str, Any], index: int | None) -> Any:
    variations = flag.get("variations") or []
    if index is None or index < 0 or index >= len(variations):
        return None
    return variations[index].get("value")


def _values_equal(a: object, b: object) -> bool:
    if a == b:
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    if isinstance(a, str) and isinstance(b, (int, float)):
        try:
            return float(a) == float(b)
        except ValueError:
            return False
    if isinstance(b, str) and isinstance(a, (int, float)):
        try:
            return float(b) == float(a)
        except ValueError:
            return False
    if isinstance(a, str) and isinstance(b, str):
        return a.strip() == b.strip()
    # JSON objects — compare canonical JSON
    if isinstance(a, (dict, list)) or isinstance(b, (dict, list)):
        try:
            left = a if isinstance(a, (dict, list)) else json.loads(str(a))
            right = b if isinstance(b, (dict, list)) else json.loads(str(b))
            return left == right
        except (TypeError, json.JSONDecodeError, ValueError):
            return False
    return False


def _normalize_fallthrough_wanted(raw: object) -> object:
    """Accept UI fallthrough as string/number/object; parse JSON strings when needed."""
    if isinstance(raw, (dict, list, bool, int, float)) or raw is None:
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return text
        if text[0] in "{[":
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        try:
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            return text
    return raw


def _variation_kind(flag: dict[str, Any]) -> str:
    values = [v.get("value") for v in (flag.get("variations") or [])]
    if not values:
        return "other"
    if all(isinstance(v, bool) for v in values):
        return "boolean"
    if all(isinstance(v, str) for v in values):
        return "string"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return "number"
    if all(isinstance(v, (dict, list)) for v in values):
        return "json"
    return "other"


def _option_token(value: object) -> str:
    """Stable string token for <option value=…> and POST fallthrough."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _variation_id_for_value(flag: dict[str, Any], wanted: object) -> str | None:
    for variation in flag.get("variations") or []:
        if _values_equal(variation.get("value"), wanted):
            vid = variation.get("_id") or variation.get("id")
            if isinstance(vid, str) and vid:
                return vid
    return None


def _summarize_flag(flag: dict[str, Any], environment_key: str, meta: dict[str, str]) -> dict[str, Any]:
    envs = flag.get("environments") or {}
    env = envs.get(environment_key) or {}
    on = bool(env.get("on"))
    off_idx = env.get("offVariation")
    fall_idx = (env.get("fallthrough") or {}).get("variation")
    rules = env.get("rules") or []
    targets = env.get("targets") or []
    context_targets = env.get("contextTargets") or []

    kind = _variation_kind(flag)
    variations_out: list[dict[str, Any]] = []
    fallthrough_options: list[dict[str, Any]] = []
    for i, variation in enumerate(flag.get("variations") or []):
        val = variation.get("value")
        item = {
            "index": i,
            "value": val,
            "name": variation.get("name") or "",
            "description": variation.get("description") or "",
            "token": _option_token(val),
        }
        variations_out.append(item)
        # Boolean on/off is handled by the toggle; options are for multivariate.
        if kind != "boolean":
            fallthrough_options.append(
                {
                    "token": item["token"],
                    "label": item["name"] or item["token"],
                    "value": val,
                }
            )

    off_value = _variation_value(flag, off_idx if isinstance(off_idx, int) else None)
    fall_value = _variation_value(flag, fall_idx if isinstance(fall_idx, int) else None)

    if on:
        if rules or targets or context_targets:
            targeting_hint = (
                "Flag is ON. Fallthrough serves "
                f"{fall_value!r}; targets/rules may override for some contexts."
            )
        else:
            targeting_hint = (
                "Flag is ON with no extra targets/rules — "
                f"evaluations use fallthrough ({fall_value!r})."
            )
    else:
        targeting_hint = (
            "Flag is OFF — evaluations receive the off variation "
            f"({off_value!r}), regardless of fallthrough."
        )

    return {
        "key": flag.get("key") or meta["key"],
        "name": flag.get("name") or meta["label"],
        "label": meta["label"],
        "summary": meta["summary"],
        "on": on,
        "variationKind": kind,
        "fallthroughOptions": fallthrough_options,
        "fallthroughToken": _option_token(fall_value) if fall_value is not None else None,
        "variations": variations_out,
        "offVariation": off_idx,
        "fallthroughVariation": fall_idx,
        "servedWhenOff": off_value,
        "servedWhenOnFallthrough": fall_value,
        "ruleCount": len(rules),
        "targetCount": len(targets) + len(context_targets),
        "targetingHint": targeting_hint,
    }


def list_flag_controls() -> dict[str, Any]:
    """Fetch on/off status + variation summary for controlled flags."""
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
                    "targetingHint": "Set missing env vars to enable controls.",
                }
                for item in CONTROLLED_FLAGS
            ],
        }

    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    assert project and environment
    query = urllib.parse.urlencode({"env": environment})
    flags_out: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for meta in CONTROLLED_FLAGS:
        key = meta["key"]
        try:
            flag = _request("GET", f"/flags/{project}/{key}?{query}")
            flags_out.append(_summarize_flag(flag, environment, meta))
        except Exception as exc:  # noqa: BLE001
            errors.append({"key": key, "error": str(exc)})
            flags_out.append(
                {
                    "key": key,
                    "label": meta["label"],
                    "summary": meta["summary"],
                    "on": None,
                    "targetingHint": str(exc),
                    "error": str(exc),
                }
            )

    return {**cfg, "flags": flags_out, "errors": errors}


def _fallthrough_instruction(flag: dict[str, Any], wanted: object) -> dict[str, Any] | None:
    vid = _variation_id_for_value(flag, wanted)
    if not vid:
        return None
    return {
        "kind": "updateFallthroughVariationOrRollout",
        "variationId": vid,
    }


def apply_flag_control(
    flag_key: str,
    *,
    turn_on: bool | None = None,
    fallthrough: object | None = None,
) -> dict[str, Any]:
    """
    Apply semantic-patch controls for a 12 lab flag.

    LaunchDarkly: turnFlagOn / turnFlagOff / updateFallthroughVariationOrRollout
    https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
    """
    if flag_key not in _ALLOWED_KEYS:
        raise ValueError(f"Flag key not allowed for controls: {flag_key}")
    if turn_on is None and fallthrough is None:
        raise ValueError('Provide "on" and/or "fallthrough"')

    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError(
            "Flag controls need " + ", ".join(cfg["missing"]) + " in the server environment."
        )
    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    assert project and environment

    query = urllib.parse.urlencode({"env": environment})
    flag = _request("GET", f"/flags/{project}/{flag_key}?{query}")

    instructions: list[dict[str, Any]] = []
    action_parts: list[str] = []
    wanted = _normalize_fallthrough_wanted(fallthrough) if fallthrough is not None else None

    if turn_on is True:
        action_parts.append("turnFlagOn")
        instructions.append({"kind": "turnFlagOn"})
        if wanted is not None:
            fall = _fallthrough_instruction(flag, wanted)
            if not fall:
                raise ValueError(f"No variation matching fallthrough={wanted!r} on {flag_key}")
            instructions.append(fall)
            action_parts.append("updateFallthrough")
    elif turn_on is False:
        action_parts.append("turnFlagOff")
        instructions.append({"kind": "turnFlagOff"})
        if wanted is not None:
            fall = _fallthrough_instruction(flag, wanted)
            if fall:
                instructions.append(fall)
                action_parts.append("updateFallthrough")
    elif wanted is not None:
        fall = _fallthrough_instruction(flag, wanted)
        if not fall:
            raise ValueError(f"No variation matching fallthrough={wanted!r} on {flag_key}")
        instructions.append(fall)
        action_parts.append("updateFallthrough")

    action = "+".join(action_parts) if action_parts else "noop"
    _request(
        "PATCH",
        f"/flags/{project}/{flag_key}",
        {
            "environmentKey": environment,
            "comment": f"12-flag-variations UI: {action}",
            "instructions": instructions,
        },
    )

    flag = _request("GET", f"/flags/{project}/{flag_key}?{query}")
    meta = next(item for item in CONTROLLED_FLAGS if item["key"] == flag_key)
    summary = _summarize_flag(flag, environment, meta)
    return {
        "ok": True,
        "action": action,
        "instructions": [i.get("kind") for i in instructions],
        "projectKey": project,
        "environmentKey": environment,
        "flag": summary,
    }
