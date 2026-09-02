"""REST controls for the two flags in 15-prerequisite-flags.

Controls may change on/off and the parent's fallthrough color. They never edit
the prerequisite relationship configured on the dependent flag.
https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from prerequisite import FLAG_COUNT, FLAG_HIGHLIGHT, VALID_COLORS

CONTROLLED_FLAGS = (
    {
        "key": FLAG_HIGHLIGHT,
        "label": "Parent · grid selection highlight",
        "summary": (
            "15-prerequisite-flags parent (cites 11's enable-grid-selection-highlight). "
            "Must be on and serving green to satisfy the prerequisite."
        ),
    },
    {
        "key": FLAG_COUNT,
        "label": "Child · navigation move count",
        "summary": (
            "15-prerequisite-flags child (cites 11's show-navigation-move-count). "
            "Unmet prerequisite serves its off variation."
        ),
    },
)
_ALLOWED_KEYS = frozenset(item["key"] for item in CONTROLLED_FLAGS)
LD_API_HOST = os.environ.get("LD_API_HOST") or "https://app.launchdarkly.com"
LD_API_VERSION = os.environ.get("LD_API_VERSION") or "20240415"


def api_config() -> dict[str, Any]:
    """Report whether REST controls are configured without exposing secrets."""
    values = {
        "LD_API_ACCESS_TOKEN": (os.environ.get("LD_API_ACCESS_TOKEN") or "").strip(),
        "LD_PROJECT_KEY": (os.environ.get("LD_PROJECT_KEY") or "").strip(),
        "LD_ENVIRONMENT_KEY": (
            os.environ.get("LD_ENVIRONMENT_KEY") or ""
        ).strip(),
    }
    missing = [key for key, value in values.items() if not value]
    return {
        "configured": not missing,
        "missing": missing,
        "projectKey": values["LD_PROJECT_KEY"] or None,
        "environmentKey": values["LD_ENVIRONMENT_KEY"] or None,
        "apiHost": LD_API_HOST,
    }


def _request(
    method: str, path: str, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Flag controls need " + ", ".join(cfg["missing"]))

    headers = {
        "Authorization": (os.environ.get("LD_API_ACCESS_TOKEN") or "").strip(),
        "LD-API-Version": LD_API_VERSION,
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = (
            "application/json; domain-model=launchdarkly.semanticpatch"
        )
    request = urllib.request.Request(
        f"{LD_API_HOST.rstrip('/')}/api/v2{path}",
        data=data,
        headers=headers,
        method=method,
    )
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
    if isinstance(index, int) and 0 <= index < len(variations):
        return variations[index].get("value")
    return None


def _variation_id(flag: dict[str, Any], wanted: object) -> str | None:
    for variation in flag.get("variations") or []:
        if variation.get("value") == wanted:
            return variation.get("_id") or variation.get("id")
    return None


def _summarize(
    flag: dict[str, Any], environment: str, meta: dict[str, str]
) -> dict[str, Any]:
    env = (flag.get("environments") or {}).get(environment) or {}
    fallthrough_index = (env.get("fallthrough") or {}).get("variation")
    prerequisites = env.get("prerequisites") or []
    prerequisite = prerequisites[0] if prerequisites else None
    values = [variation.get("value") for variation in flag.get("variations") or []]
    return {
        "key": meta["key"],
        "label": meta["label"],
        "summary": meta["summary"],
        "on": bool(env.get("on")),
        "variationKind": (
            "string"
            if values and all(isinstance(value, str) for value in values)
            else "boolean"
        ),
        "colorOptions": (
            [value for value in values if value in VALID_COLORS]
            if meta["key"] == FLAG_HIGHLIGHT
            else []
        ),
        "servedWhenOff": _variation_value(flag, env.get("offVariation")),
        "servedWhenOnFallthrough": _variation_value(flag, fallthrough_index),
        "prerequisite": prerequisite,
        "prerequisiteConfigured": (
            meta["key"] != FLAG_COUNT
            or bool(
                prerequisite
                and prerequisite.get("key") == FLAG_HIGHLIGHT
            )
        ),
        "targetingHint": (
            "Required by child: parent must be ON and serve green."
            if meta["key"] == FLAG_HIGHLIGHT
            else (
                "Prerequisite configured; lab controls leave it unchanged."
                if prerequisite
                else "Missing prerequisite — run this example's provisioning."
            )
        ),
    }


def list_flag_controls() -> dict[str, Any]:
    """Fetch parent/child status and expose the child's prerequisite evidence."""
    cfg = api_config()
    if not cfg["configured"]:
        return {
            **cfg,
            "flags": [
                {
                    **meta,
                    "on": None,
                    "targetingHint": "Set missing environment variables.",
                }
                for meta in CONTROLLED_FLAGS
            ],
        }

    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flags = []
    errors = []
    for meta in CONTROLLED_FLAGS:
        try:
            flag = _request(
                "GET", f"/flags/{project}/{meta['key']}?{query}"
            )
            flags.append(_summarize(flag, environment, meta))
        except Exception as exc:  # noqa: BLE001
            errors.append({"key": meta["key"], "error": str(exc)})
            flags.append(
                {
                    **meta,
                    "on": None,
                    "targetingHint": str(exc),
                    "error": str(exc),
                }
            )
    return {**cfg, "flags": flags, "errors": errors}


def apply_flag_control(
    flag_key: str,
    *,
    turn_on: bool | None = None,
    fallthrough_value: str | None = None,
) -> dict[str, Any]:
    """Apply allowed semantic patches while preserving prerequisites."""
    if flag_key not in _ALLOWED_KEYS:
        raise ValueError(f"Flag key not allowed for controls: {flag_key}")
    if turn_on is None and fallthrough_value is None:
        raise ValueError('Provide "on" and/or "fallthrough"')
    if fallthrough_value is not None and flag_key != FLAG_HIGHLIGHT:
        raise ValueError("Only the parent highlight flag has color variations")

    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Flag controls need " + ", ".join(cfg["missing"]))
    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flag = _request("GET", f"/flags/{project}/{flag_key}?{query}")

    instructions: list[dict[str, Any]] = []
    if turn_on is not None:
        instructions.append(
            {"kind": "turnFlagOn" if turn_on else "turnFlagOff"}
        )
    if fallthrough_value is not None:
        variation_id = _variation_id(flag, fallthrough_value)
        if not variation_id:
            raise ValueError(
                f"No variation matching fallthrough={fallthrough_value!r}"
            )
        instructions.append(
            {
                "kind": "updateFallthroughVariationOrRollout",
                "variationId": variation_id,
            }
        )

    _request(
        "PATCH",
        f"/flags/{project}/{flag_key}",
        {
            "environmentKey": environment,
            "comment": "15-prerequisite-flags UI control",
            "instructions": instructions,
        },
    )
    updated = _request("GET", f"/flags/{project}/{flag_key}?{query}")
    meta = next(item for item in CONTROLLED_FLAGS if item["key"] == flag_key)
    return {
        "ok": True,
        "instructions": [item["kind"] for item in instructions],
        "projectKey": project,
        "environmentKey": environment,
        "flag": _summarize(updated, environment, meta),
    }
