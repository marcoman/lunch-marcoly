#!/usr/bin/env python3
"""Serve the adaptive-trigger grid while keeping privileged controls server-side."""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from highlight_eval import FLAG_HIGHLIGHT, build_context, evaluate_highlight  # noqa: E402

PORT = int(os.environ.get("PORT", "8161"))
ROOT = Path(__file__).resolve().parent
FLAG_NAME = "Enable: adaptive grid highlight"
METRIC_KEY = "adaptive-grid-nav-latency-metric"
EVENT_KEY = "adaptive-grid-nav-latency"
THRESHOLD_MS = 200
LIVE_VALUE = "green"
API_HOST = os.environ.get("LD_API_HOST", "https://app.launchdarkly.com").rstrip("/")
APP_HOST = os.environ.get("LD_APP_HOST", API_HOST).rstrip("/")

_ld_client: LDClient | None = None
_cached_sdk_environment_key: str | None = None


class ApiError(Exception):
    """An HTTP-safe error returned by a local API route."""

    def __init__(self, message: str, status: int = 500) -> None:
        super().__init__(message)
        self.status = status


def wait_for_ld(client: LDClient, timeout: float = 10.0) -> bool:
    """Wait briefly for the server-side SDK data source to initialize."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.is_initialized():
            return True
        time.sleep(0.05)
    return client.is_initialized()


def init_launchdarkly() -> None:
    """Initialize server-side flag evaluation and custom metric delivery.

    LaunchDarkly: server-side SDK initialization and event delivery.
    https://launchdarkly.com/docs/sdk/server-side/python
    """
    global _ld_client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        print(
            "Warning: LD_SDK_KEY is unset — evaluation stays at code fallback none.",
            file=sys.stderr,
        )
        return
    ldclient.set_config(Config(sdk_key))
    client = ldclient.get()
    if wait_for_ld(client):
        _ld_client = client
    else:
        print("Warning: LaunchDarkly initialization failed.", file=sys.stderr)
        client.close()


def api_config() -> dict[str, Any]:
    """Describe credentials needed by privileged LaunchDarkly REST controls."""
    keys = ("LD_API_ACCESS_TOKEN", "LD_PROJECT_KEY", "LD_ENVIRONMENT_KEY")
    missing = [key for key in keys if not os.environ.get(key, "").strip()]
    return {
        "configured": not missing,
        "missing": missing,
        "projectKey": os.environ.get("LD_PROJECT_KEY") or None,
        "environmentKey": os.environ.get("LD_ENVIRONMENT_KEY") or None,
    }


def dashboard_links(
    project_key: str | None, environment_key: str | None
) -> dict[str, str] | None:
    """Build deep links to flag targeting, monitoring, metrics, and environments."""
    if not project_key:
        return None
    encoded_project = quote(project_key, safe="")
    encoded_flag = quote(FLAG_HIGHLIGHT, safe="")
    env_query = ""
    if environment_key:
        env_query = "?" + urlencode(
            {"env": environment_key, "selected-env": environment_key}
        )
    flag_base = f"{APP_HOST}/projects/{encoded_project}/flags/{encoded_flag}"
    return {
        "flagTargeting": f"{flag_base}{env_query}",
        "flagMonitoring": f"{flag_base}/monitoring{env_query}",
        "metric": (
            f"{APP_HOST}/projects/{encoded_project}/metrics/"
            f"{quote(METRIC_KEY, safe='')}"
        ),
        "environments": (
            f"{APP_HOST}/projects/{encoded_project}/settings/environments"
        ),
    }


def ld_api(
    pathname: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    content_type: str = "application/json",
) -> dict[str, Any]:
    """Call LaunchDarkly REST APIs without exposing the access token to the page.

    LaunchDarkly API authentication:
    https://launchdarkly.com/docs/api
    """
    config = api_config()
    if not config["configured"]:
        raise ApiError(
            f"This control needs {', '.join(config['missing'])} on the Python host.",
            503,
        )
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        f"{API_HOST}/api/v2{pathname}",
        data=data,
        method=method,
        headers={
            "Authorization": os.environ["LD_API_ACCESS_TOKEN"],
            "LD-API-Version": "20240415",
            "Content-Type": content_type,
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = response.read()
            return json.loads(payload) if payload else {}
    except HTTPError as error:
        try:
            payload = json.loads(error.read())
            message = payload.get("message")
        except (json.JSONDecodeError, AttributeError):
            message = None
        raise ApiError(
            message or f"LaunchDarkly API returned {error.code}", error.code
        ) from error


def resolve_sdk_environment_key() -> str | None:
    """Find which environment owns LD_SDK_KEY to diagnose silent mismatches."""
    global _cached_sdk_environment_key
    if _cached_sdk_environment_key:
        return _cached_sdk_environment_key
    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    config = api_config()
    if not sdk_key or not config["configured"]:
        return None
    body = ld_api(
        f"/projects/{quote(str(config['projectKey']), safe='')}/environments?limit=100"
    )
    match = next(
        (item for item in body.get("items", []) if item.get("apiKey") == sdk_key),
        None,
    )
    _cached_sdk_environment_key = match.get("key") if match else None
    return _cached_sdk_environment_key


def fetch_last_change() -> dict[str, Any] | None:
    """Attribute the latest flag update through the LaunchDarkly audit log.

    LaunchDarkly: audit log entries.
    https://launchdarkly.com/docs/api/audit-log/get-audit-log-entries
    """
    config = api_config()
    spec = (
        f"proj/{config['projectKey']}:env/{config['environmentKey']}:"
        f"flag/{FLAG_HIGHLIGHT}"
    )
    body = ld_api(f"/auditlog?{urlencode({'spec': spec, 'limit': 1})}")
    entries = body.get("items", [])
    if not entries:
        return None
    entry = entries[0]
    actor = (entry.get("member") or {}).get("email") or (
        entry.get("token") or {}
    ).get("name")
    raw_summary = str(entry.get("description") or entry.get("titleVerb") or "")
    summary = "; ".join(
        line.strip()
        for line in raw_summary.translate(str.maketrans("", "", "*~`")).splitlines()
        if line.strip()
    )
    return {
        "date": entry.get("date"),
        "summary": summary,
        "actor": actor,
        "byAutomation": not actor,
    }


def get_status() -> dict[str, Any]:
    """Read current targeting plus best-effort environment and audit diagnostics."""
    config = api_config()
    links = dashboard_links(config["projectKey"], config["environmentKey"])
    sdk: dict[str, Any] = {
        "initialized": _ld_client is not None,
        "environmentKey": None,
        "matchesRestEnvironment": None,
    }
    if not config["configured"]:
        return {**config, "links": links, "sdk": sdk, "flag": None}

    project = quote(str(config["projectKey"]), safe="")
    flag = ld_api(f"/flags/{project}/{quote(FLAG_HIGHLIGHT, safe='')}")
    targeting = (flag.get("environments") or {}).get(config["environmentKey"])
    fallthrough_index = ((targeting or {}).get("fallthrough") or {}).get("variation")
    fallthrough = None
    if isinstance(fallthrough_index, int):
        variations = flag.get("variations") or []
        if 0 <= fallthrough_index < len(variations):
            fallthrough = variations[fallthrough_index].get("value")

    last_change = None
    try:
        sdk["environmentKey"] = resolve_sdk_environment_key()
        if sdk["environmentKey"]:
            sdk["matchesRestEnvironment"] = (
                sdk["environmentKey"] == config["environmentKey"]
            )
        last_change = fetch_last_change()
    except Exception:
        pass
    return {
        **config,
        "links": links,
        "sdk": sdk,
        "lastChange": last_change,
        "flag": {
            "key": FLAG_HIGHLIGHT,
            "name": flag.get("name") or FLAG_NAME,
            "on": targeting.get("on") if targeting else None,
            "fallthrough": fallthrough,
        },
    }


def start_live() -> dict[str, Any]:
    """Turn targeting on and select green for the default rule."""
    config = api_config()
    project = quote(str(config["projectKey"]), safe="")
    flag_path = f"/flags/{project}/{quote(FLAG_HIGHLIGHT, safe='')}"
    flag = ld_api(flag_path)
    live = next(
        (variation for variation in flag.get("variations", []) if variation.get("value") == LIVE_VALUE),
        None,
    )
    if live is None:
        raise ApiError(f"Flag {FLAG_HIGHLIGHT} has no {LIVE_VALUE} variation.", 409)
    ld_api(
        flag_path,
        method="PATCH",
        content_type="application/json; domain-model=launchdarkly.semanticpatch",
        body={
            "environmentKey": config["environmentKey"],
            "comment": "16-adaptive-triggers: start live from lab control",
            "instructions": [
                {"kind": "turnFlagOn"},
                {
                    "kind": "updateFallthroughVariationOrRollout",
                    "variationId": live["_id"],
                },
            ],
        },
    )
    return get_status()


def stop_live() -> dict[str, Any]:
    """Turn targeting off while leaving the adaptive trigger configured."""
    config = api_config()
    project = quote(str(config["projectKey"]), safe="")
    ld_api(
        f"/flags/{project}/{quote(FLAG_HIGHLIGHT, safe='')}",
        method="PATCH",
        content_type="application/json; domain-model=launchdarkly.semanticpatch",
        body={
            "environmentKey": config["environmentKey"],
            "comment": "16-adaptive-triggers: stop from lab control",
            "instructions": [{"kind": "turnFlagOff"}],
        },
    )
    return get_status()


def track_latency(username: str, latency_ms: object) -> dict[str, Any]:
    """Send a numeric custom metric event for adaptive-trigger monitoring.

    LaunchDarkly: custom events with numeric metric values.
    https://launchdarkly.com/docs/sdk/features/events
    """
    if _ld_client is None:
        raise ApiError("LD_SDK_KEY is missing or the SDK did not initialize.", 503)
    try:
        value = float(latency_ms)
    except (TypeError, ValueError):
        value = float("nan")
    if not username or not 0 <= value <= 500:
        raise ApiError("username and latencyMs (0–500) are required.", 400)
    _ld_client.track(
        EVENT_KEY,
        build_context(username),
        {"source": "16-adaptive-triggers"},
        value,
    )
    _ld_client.flush()
    return {
        "tracked": True,
        "eventKey": EVENT_KEY,
        "latencyMs": value,
        "aboveThreshold": value > THRESHOLD_MS,
    }


class Handler(SimpleHTTPRequestHandler):
    """Serve the static rail and the Node-compatible local JSON API."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(length)) if length else {}
        except (ValueError, json.JSONDecodeError) as error:
            raise ApiError(str(error), 500) from error

    def api_config_response(self) -> dict[str, Any]:
        config = api_config()
        return {
            "controls": config,
            "flag": {"key": FLAG_HIGHLIGHT, "name": FLAG_NAME},
            "metricKey": METRIC_KEY,
            "eventKey": EVENT_KEY,
            "thresholdMs": THRESHOLD_MS,
            "links": dashboard_links(config["projectKey"], config["environmentKey"]),
        }

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/config":
                self.send_json(200, self.api_config_response())
                return
            if parsed.path == "/api/highlight":
                username = (parse_qs(parsed.query).get("username") or [""])[0].strip()
                if not username:
                    raise ApiError("username query parameter is required", 400)
                self.send_json(200, evaluate_highlight(_ld_client, username))
                return
            if parsed.path == "/api/status":
                self.send_json(200, get_status())
                return
            if parsed.path.startswith("/api/"):
                self.send_json(404, {"error": "Not found"})
                return
            super().do_GET()
        except Exception as error:
            self.send_json(
                getattr(error, "status", 500), {"error": str(error)}
            )

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/start-live":
                self.send_json(200, start_live())
            elif parsed.path == "/api/stop":
                self.send_json(200, stop_live())
            elif parsed.path == "/api/track-latency":
                body = self.read_json()
                self.send_json(
                    200,
                    track_latency(
                        str(body.get("username") or "").strip(),
                        body.get("latencyMs"),
                    ),
                )
            else:
                self.send_json(404, {"error": "Not found"})
        except Exception as error:
            self.send_json(
                getattr(error, "status", 500), {"error": str(error)}
            )


def close_launchdarkly(*_args: object) -> None:
    """Flush and close the SDK before process exit."""
    if _ld_client is not None:
        _ld_client.close()


def run_server() -> None:
    """Start the local web twin on the adaptive-trigger port."""
    init_launchdarkly()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("16-adaptive-triggers[python]")
    print(f"Flag: {FLAG_NAME} ({FLAG_HIGHLIGHT})")
    print(f"Metric event key: {EVENT_KEY} — threshold {THRESHOLD_MS} ms")
    print(f"Open http://127.0.0.1:{PORT}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        close_launchdarkly()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--evaluate-once":
        init_launchdarkly()
        try:
            print(json.dumps(evaluate_highlight(_ld_client, sys.argv[2])))
        finally:
            close_launchdarkly()
    else:
        run_server()
