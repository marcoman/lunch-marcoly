"""LaunchDarkly REST helpers for in-app flag on/off controls (11-flag-enablement).

Uses the Feature flags PATCH API with semantic patch turnFlagOn / turnFlagOff.
Does not edit variation definitions — only environment targeting on/off + status.

REST API — feature flags
https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
https://launchdarkly.com/docs/guides/api/rest-api
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from highlight_style import (
    DEFAULT_STRING_ON_COLOR,
    FLAG_CONTEXT,
    FLAG_COUNT,
    FLAG_HIGHLIGHT,
    is_highlight_off_value,
)
from host_os import FLAG_OS_EMOJI

# Flags this example is allowed to toggle.
CONTROLLED_FLAGS: list[dict[str, str]] = [
    {
        "key": FLAG_HIGHLIGHT,
        "label": "Selection highlight",
        "summary": (
            "Colored X on the selected cell. String flag: off→none, on→green "
            "(or the current fallthrough color). Boolean flag: true/false."
        ),
    },
    {
        "key": FLAG_CONTEXT,
        "label": "Context highlight colors",
        "summary": "Cohort colors from words in the username (human / robot / beta).",
    },
    {
        "key": FLAG_COUNT,
        "label": "Move count",
        "summary": "Show Count: N in the header.",
    },
    {
        "key": FLAG_OS_EMOJI,
        "label": "Host OS emoji",
        "summary": "OS emoji before the username (private hostOs attribute).",
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


def _summarize_flag(flag: dict[str, Any], environment_key: str, meta: dict[str, str]) -> dict[str, Any]:
    envs = flag.get("environments") or {}
    env = envs.get(environment_key) or {}
    on = bool(env.get("on"))
    off_idx = env.get("offVariation")
    fall_idx = (env.get("fallthrough") or {}).get("variation")
    rules = env.get("rules") or []
    targets = env.get("targets") or []
    context_targets = env.get("contextTargets") or []

    variations_out: list[dict[str, Any]] = []
    for i, variation in enumerate(flag.get("variations") or []):
        variations_out.append(
            {
                "index": i,
                "value": variation.get("value"),
                "name": variation.get("name") or "",
                "description": variation.get("description") or "",
            }
        )

    off_value = _variation_value(flag, off_idx if isinstance(off_idx, int) else None)
    fall_value = _variation_value(flag, fall_idx if isinstance(fall_idx, int) else None)

    if on:
        if rules or targets or context_targets:
            targeting_hint = (
                "Flag is ON. Fallthrough serves "
                f"{fall_value!r}; individual targets/rules may override for some contexts."
            )
        else:
            targeting_hint = (
                "Flag is ON with no extra targets/rules in this environment — "
                f"evaluations use the fallthrough variation ({fall_value!r})."
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
        except Exception as exc:  # noqa: BLE001 — surface per-flag failures in UI
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


def _variation_id_for_value(flag: dict[str, Any], wanted: object) -> str | None:
    for variation in flag.get("variations") or []:
        if variation.get("value") == wanted:
            vid = variation.get("_id") or variation.get("id")
            if isinstance(vid, str) and vid:
                return vid
    return None


def _is_string_variations(flag: dict[str, Any]) -> bool:
    values = [v.get("value") for v in (flag.get("variations") or [])]
    return bool(values) and all(isinstance(v, str) for v in values)


def _highlight_on_instructions(flag: dict[str, Any]) -> list[dict[str, Any]]:
    """
    turnFlagOn, and for string highlight flags ensure fallthrough is not "none".

    Does not add/remove variations — only picks an existing color variation as fallthrough.
    """
    instructions: list[dict[str, Any]] = [{"kind": "turnFlagOn"}]
    if flag.get("key") != FLAG_HIGHLIGHT or not _is_string_variations(flag):
        return instructions

    envs = flag.get("environments") or {}
    # Environment block may be missing on unfiltered GET; still set fallthrough.
    preferred = DEFAULT_STRING_ON_COLOR
    color_id = _variation_id_for_value(flag, preferred)
    if not color_id:
        for variation in flag.get("variations") or []:
            val = variation.get("value")
            if isinstance(val, str) and not is_highlight_off_value(val):
                color_id = variation.get("_id") or variation.get("id")
                preferred = val
                break
    if not color_id:
        return instructions

    # Only rewrite fallthrough when it currently serves an off-like value.
    # (Caller passes a freshly fetched flag; fallthrough index may be absent.)
    fall_idx = None
    for env in envs.values():
        fall_idx = (env.get("fallthrough") or {}).get("variation")
        if fall_idx is not None:
            break
    fall_value = _variation_value(flag, fall_idx if isinstance(fall_idx, int) else None)
    if fall_value is not None and not is_highlight_off_value(fall_value):
        return instructions

    instructions.append(
        {
            "kind": "updateFallthroughVariationOrRollout",
            "variationId": color_id,
        }
    )
    return instructions


def set_flag_on(flag_key: str, turn_on: bool) -> dict[str, Any]:
    """
    Turn a controlled flag on or off in LD_ENVIRONMENT_KEY via semantic patch.

    LaunchDarkly: turnFlagOn / turnFlagOff — does not change variation definitions.
    For the string highlight flag, turning ON also sets fallthrough to a color
    when fallthrough is still "none" (otherwise on/off look identical).
    """
    if flag_key not in _ALLOWED_KEYS:
        raise ValueError(f"Flag key not allowed for controls: {flag_key}")

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

    if turn_on:
        kind = "turnFlagOn"
        instructions = _highlight_on_instructions(flag)
    else:
        kind = "turnFlagOff"
        instructions = [{"kind": kind}]

    _request(
        "PATCH",
        f"/flags/{project}/{flag_key}",
        {
            "environmentKey": environment,
            "comment": f"11-flag-enablement UI: {kind}",
            "instructions": instructions,
        },
    )

    flag = _request("GET", f"/flags/{project}/{flag_key}?{query}")
    meta = next(item for item in CONTROLLED_FLAGS if item["key"] == flag_key)
    summary = _summarize_flag(flag, environment, meta)
    return {
        "ok": True,
        "action": kind,
        "instructions": [i.get("kind") for i in instructions],
        "projectKey": project,
        "environmentKey": environment,
        "flag": summary,
    }
