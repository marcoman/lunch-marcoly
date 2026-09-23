"""LaunchDarkly evaluation and REST helpers for scheduled flag changes.

Scheduled changes API:
https://launchdarkly.com/docs/api/scheduled-changes
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ldclient.client import LDClient
from ldclient.context import Context

FLAG_KEY = "enable-grid-selection-highlight-sched"
DEFAULT_VALUE = "none"
LD_API_HOST = os.environ.get("LD_API_HOST") or "https://app.launchdarkly.com"
LD_API_VERSION = os.environ.get("LD_API_VERSION") or "20240415"


def normalize_username(value: str) -> str:
    """Use the trimmed login name as the LaunchDarkly user context key."""
    username = value.strip()
    if not username:
        raise ValueError("Username is required.")
    return username


def evaluate_highlight(client: LDClient | None, username: str) -> dict[str, Any]:
    """Evaluate the highlight; LaunchDarkly applies the scheduled on change."""
    username = normalize_username(username)
    context = Context.builder(username).kind("user").name(username).build()
    if client is None or not client.is_initialized():
        return {
            "flagKey": FLAG_KEY,
            "flagValue": DEFAULT_VALUE,
            "highlightColor": DEFAULT_VALUE,
            "variationIndex": None,
            "reason": {"kind": "ERROR", "errorKind": "CLIENT_NOT_READY"},
            "ldContext": {"kind": "user", "key": username, "name": username},
        }

    detail = client.variation_detail(FLAG_KEY, context, DEFAULT_VALUE)
    value = detail.value if detail.value in {"none", "green"} else DEFAULT_VALUE
    return {
        "flagKey": FLAG_KEY,
        "flagValue": value,
        "highlightColor": value,
        "variationIndex": detail.variation_index,
        "reason": detail.reason,
        "ldContext": {"kind": "user", "key": username, "name": username},
    }


def api_config() -> dict[str, Any]:
    """Report REST configuration without exposing the access token."""
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
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    semantic_patch: bool = False,
) -> dict[str, Any]:
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Scheduled changes need " + ", ".join(cfg["missing"]))

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
            if semantic_patch
            else "application/json"
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


def _base_path() -> str:
    cfg = api_config()
    project = urllib.parse.quote(str(cfg["projectKey"] or ""), safe="")
    environment = urllib.parse.quote(str(cfg["environmentKey"] or ""), safe="")
    flag = urllib.parse.quote(FLAG_KEY, safe="")
    return (
        f"/projects/{project}/flags/{flag}/environments/{environment}"
        "/scheduled-changes"
    )


def _delete_pending_changes() -> int:
    """Delete every pending scheduled change for this lesson's flag."""
    base = _base_path()
    deleted = 0
    for item in _request("GET", base).get("items") or []:
        change_id = item.get("_id")
        if change_id:
            _request("DELETE", f"{base}/{urllib.parse.quote(change_id, safe='')}")
            deleted += 1
    return deleted


def _turn_flag_off(comment: str) -> None:
    """Turn the flag off now with a semantic patch, independent of schedules."""
    cfg = api_config()
    project = urllib.parse.quote(str(cfg["projectKey"]), safe="")
    flag = urllib.parse.quote(FLAG_KEY, safe="")
    _request(
        "PATCH",
        f"/flags/{project}/{flag}",
        {
            "environmentKey": str(cfg["environmentKey"]),
            "comment": comment,
            "instructions": [{"kind": "turnFlagOff"}],
        },
        semantic_patch=True,
    )


def list_scheduled_changes() -> dict[str, Any]:
    """List pending changes for the dedicated lesson flag."""
    cfg = api_config()
    if not cfg["configured"]:
        return {**cfg, "items": []}
    response = _request("GET", _base_path())
    items = sorted(
        response.get("items") or [], key=lambda item: item.get("executionDate") or 0
    )
    return {
        **cfg,
        "items": [
            {
                "id": item.get("_id"),
                "createdAt": item.get("_creationDate"),
                "executionDate": item.get("executionDate"),
                "instructions": item.get("instructions") or [],
            }
            for item in items
        ],
    }


def start_scheduled_change(minutes: int) -> dict[str, Any]:
    """Replace pending changes, reset the flag off, then schedule it on.

    Resetting first makes repeated classroom runs visible: X-only now, green
    after LaunchDarkly executes the scheduled ``turnFlagOn`` instruction.
    """
    if minutes < 1 or minutes > 60:
        raise ValueError("minutes must be between 1 and 60")

    deleted = _delete_pending_changes()
    _turn_flag_off("17-scheduled-changes: reset off before starting demo")

    now_ms = int(time.time() * 1000)
    execution_date = now_ms + minutes * 60_000
    created = _request(
        "POST",
        _base_path(),
        {
            "executionDate": execution_date,
            "instructions": [{"kind": "turnFlagOn"}],
            "comment": (
                f"17-scheduled-changes: turn highlight on after {minutes} minute(s)"
            ),
        },
    )
    return {
        "ok": True,
        "replacedCount": deleted,
        "minutes": minutes,
        "startedAt": now_ms,
        "scheduledChange": {
            "id": created.get("_id"),
            "createdAt": created.get("_creationDate") or now_ms,
            "executionDate": created.get("executionDate") or execution_date,
            "instructions": created.get("instructions")
            or [{"kind": "turnFlagOn"}],
        },
    }


def stop_scheduled_change() -> dict[str, Any]:
    """Cancel pending changes and turn the flag off in one operation.

    Cancelling alone would leave an already-executed change on, and turning
    off alone would let a still-pending change flip it back on later.
    """
    cancelled = _delete_pending_changes()
    _turn_flag_off("17-scheduled-changes: stop demo and turn highlight off")
    return {
        "ok": True,
        "cancelledCount": cancelled,
        "stoppedAt": int(time.time() * 1000),
    }
