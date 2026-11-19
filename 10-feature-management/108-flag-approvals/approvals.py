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
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

FLAG_KEY = "show-navigation-move-count-approval"
DESCRIPTION = "Turn on the move count"


class ApprovalError(RuntimeError):
    """A LaunchDarkly call failed after some reset steps already ran."""

    def __init__(self, message: str, steps: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.steps = steps or []

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
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LaunchDarkly request failed: {exc.reason}") from exc


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


def _next_description() -> str:
    """Next approval name, shared with the Node, Java, and .NET labs.

    `.request-count` in this directory holds the last number issued.
    Reset does not change it, so a later request does not reuse a name.
    """
    root = Path(__file__).resolve().parent
    counter = root / ".request-count"
    lock = root / ".request-count.lock"
    deadline = time.time() + 2
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.time() <= deadline:
                time.sleep(0.05)
                continue
            try:
                stale = time.time() - lock.stat().st_mtime > 5
            except FileNotFoundError:
                continue
            if not stale:
                raise RuntimeError("Approval counter is locked.")
            lock.unlink(missing_ok=True)
    try:
        current = 0
        if counter.is_file():
            raw = counter.read_text().strip()
            if raw.isdigit():
                current = int(raw)
        nxt = current + 1
        temporary = root / ".request-count.tmp"
        temporary.write_text(f"{nxt}\n")
        temporary.replace(counter)
    finally:
        lock.unlink(missing_ok=True)
    return f"{DESCRIPTION} · {nxt}"


def request_approval() -> dict[str, Any]:
    """Ask for approval to turn the flag on. Reuse a request that is already open.

    LaunchDarkly: approval request · semantic patch turnFlagOn
    https://launchdarkly.com/docs/api/approvals/post-approval-request-for-a-flag
    """
    current = approval_state()
    existing = current.get("request") or {}
    if existing and existing.get("reviewStatus") != "declined" and not existing.get("applied"):
        current["steps"] = [{
            "where": "Lab API",
            "text": "Open request reused. LaunchDarkly was not asked for a second one.",
        }]
        return current
    cfg = api_config()
    description = _next_description()
    created = _request(
        "POST",
        _flag_path(cfg),
        {
            "description": description,
            "comment": "108-flag-approvals",
            "instructions": [{"kind": "turnFlagOn"}],
        },
        semantic=True,
    )
    summary = _summary(created)
    return {
        **cfg,
        "ok": True,
        "request": summary,
        "steps": [{
            "where": "LaunchDarkly",
            "text": f"POST approval-requests · turnFlagOn · {description} · review {summary['reviewStatus']}",
        }],
    }


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
    summary = _summary(applied)
    return {
        **cfg,
        "ok": True,
        "request": summary,
        "steps": [{
            "where": "LaunchDarkly",
            "text": f"POST approval-requests/{request_id}/apply · status {summary['status']}",
        }],
    }


def _listed_requests(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Open requests from the flag, plus completed ones the flag list omits."""
    found: dict[str, dict[str, Any]] = {}

    def add(payload: Any) -> None:
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return
        for item in items:
            if isinstance(item, dict) and item.get("_id"):
                found[str(item["_id"])] = item

    add(_request("GET", _flag_path(cfg)))
    resource = f"proj/{cfg['projectKey']}:env/{cfg['environmentKey']}:flag/{FLAG_KEY}"
    query = urllib.parse.quote(f"resourceId equals {resource}")
    try:
        add(_request("GET", f"/approval-requests?limit=20&filter={query}"))
    except RuntimeError:
        pass
    return list(found.values())


def reset_demo() -> dict[str, Any]:
    """Delete this flag's approval requests and turn the flag off.

    LaunchDarkly: delete approval request · semantic patch turnFlagOff
    https://launchdarkly.com/docs/api/approvals/delete-approval-request-for-a-flag
    https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
    """
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Approvals need " + ", ".join(cfg["missing"]) + ".")
    steps: list[dict[str, str]] = []
    items = _listed_requests(cfg)
    if not items:
        steps.append({"where": "LaunchDarkly", "text": "GET approval-requests · none to delete"})
    for item in items:
        if not isinstance(item, dict):
            continue
        request_id = str(item.get("_id") or "")
        if not request_id:
            continue
        try:
            _request("DELETE", f"{_flag_path(cfg)}/{request_id}")
            steps.append({
                "where": "LaunchDarkly",
                "text": f"DELETE approval-requests/{request_id}",
            })
        except RuntimeError as exc:
            steps.append({
                "where": "LaunchDarkly",
                "text": f"DELETE approval-requests/{request_id} · {exc}",
            })
    try:
        patched = _request(
            "PATCH",
            f"/flags/{cfg['projectKey']}/{FLAG_KEY}",
            {
                "environmentKey": cfg["environmentKey"],
                "comment": "108-flag-approvals reset",
                "instructions": [{"kind": "turnFlagOff"}],
            },
            semantic=True,
        )
    except RuntimeError as exc:
        raise ApprovalError(str(exc), steps) from exc
    on = None
    environments = patched.get("environments") if isinstance(patched, dict) else None
    if isinstance(environments, dict):
        environment = environments.get(cfg["environmentKey"]) or {}
        if isinstance(environment, dict):
            on = environment.get("on")
    steps.append({
        "where": "LaunchDarkly",
        "text": f"PATCH flag · turnFlagOff · on {on}",
    })
    return {**cfg, "ok": True, "request": None, "steps": steps}
