"""Approval request for the move-count flag.

The page asks LaunchDarkly to turn the flag on. A person approves that
request in LaunchDarkly. This module applies it only after that review.

Approvals
https://launchdarkly.com/docs/home/releases/approvals

Create an approval request for a flag
https://launchdarkly.com/docs/api/approvals/post-approval-request-for-a-flag
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

FLAG_KEY = "show-navigation-move-count-approval"
DESCRIPTION = "Turn on the move count"

LD_API_HOST = os.environ.get("LD_API_HOST") or "https://app.launchdarkly.com"
LD_API_VERSION = os.environ.get("LD_API_VERSION") or "20240415"


def api_config() -> dict[str, Any]:
    """Return whether the approval API can be called. No secrets."""
    token = (os.environ.get("LD_API_ACCESS_TOKEN") or "").strip()
    project = (os.environ.get("LD_PROJECT_KEY") or "").strip()
    environment = (os.environ.get("LD_ENVIRONMENT_KEY") or "").strip()
    missing = []
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
        "flagKey": FLAG_KEY,
        "appOrigin": LD_API_HOST.rstrip("/"),
    }


def _request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    semantic: bool = False,
) -> Any:
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Approvals need " + ", ".join(cfg["missing"]) + ".")
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
            if semantic
            else "application/json"
        )
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"LaunchDarkly {exc.code}: {detail[:300]}") from exc


def _summary(item: dict[str, Any]) -> dict[str, Any]:
    """The fields the rail shows. No member ids."""
    applied = item.get("appliedDate") is not None or item.get("status") == "completed"
    return {
        "id": item.get("_id"),
        "reviewStatus": item.get("reviewStatus") or "pending",
        "status": item.get("status") or "pending",
        "applied": bool(applied),
        "description": item.get("description") or DESCRIPTION,
    }


def _current_request(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The newest open request, or the newest decline if nothing is open."""
    ranked = []
    for item in items:
        summary = _summary(item)
        if summary["applied"] or summary["status"] in ("completed", "failed"):
            continue
        ranked.append((item.get("creationDate") or 0, summary))
    if not ranked:
        return None
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    for _, summary in ranked:
        if summary["reviewStatus"] != "declined":
            return summary
    return ranked[0][1]


def _flag_path(cfg: dict[str, Any]) -> str:
    return (
        f"/projects/{cfg['projectKey']}/flags/{FLAG_KEY}"
        f"/environments/{cfg['environmentKey']}/approval-requests"
    )


def approval_state() -> dict[str, Any]:
    """Current request for this flag, if one is still open."""
    cfg = api_config()
    if not cfg["configured"]:
        return {**cfg, "ok": True, "request": None}
    payload = _request("GET", _flag_path(cfg))
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        items = []
    return {**cfg, "ok": True, "request": _current_request(items)}


def request_approval() -> dict[str, Any]:
    """Ask for approval to turn the flag on. Reuse a request that is already open.

    LaunchDarkly: approval request · semantic patch turnFlagOn
    https://launchdarkly.com/docs/api/approvals/post-approval-request-for-a-flag
    """
    current = approval_state()
    existing = current.get("request") or {}
    if existing and existing.get("reviewStatus") != "declined" and not existing.get("applied"):
        return current
    cfg = api_config()
    created = _request(
        "POST",
        _flag_path(cfg),
        {
            "description": DESCRIPTION,
            "comment": "108-flag-approvals",
            "instructions": [{"kind": "turnFlagOn"}],
        },
        semantic=True,
    )
    return {**cfg, "ok": True, "request": _summary(created)}


def apply_approval(request_id: str) -> dict[str, Any]:
    """Apply a request that a reviewer has already approved.

    LaunchDarkly: apply approval request
    https://launchdarkly.com/docs/api/approvals/apply-approval-request-for-a-flag
    """
    request_id = request_id.strip()
    if not request_id:
        raise ValueError("Approval id is required")
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Approvals need " + ", ".join(cfg["missing"]) + ".")
    applied = _request(
        "POST",
        f"{_flag_path(cfg)}/{request_id}/apply",
        {"comment": "108-flag-approvals apply"},
    )
    return {**cfg, "ok": True, "request": _summary(applied)}
