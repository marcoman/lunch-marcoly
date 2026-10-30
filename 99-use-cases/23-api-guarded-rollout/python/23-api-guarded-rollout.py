#!/usr/bin/env python3
"""Serve the API guarded-rollout grid.

This process evaluates the flag and sends the latency and movement events.
Start guarded release POSTs the environment release. The slider chooses
the latency value. Error-rate events are not sent.

LaunchDarkly: guarded rollout via environment releases
https://launchdarkly.com/docs/api/environment-releases
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from highlight_eval import FLAG_HIGHLIGHT, evaluate_highlight  # noqa: E402
from metrics import LATENCY_THRESHOLD_MS, metric_views, track_observed  # noqa: E402
from release_status import (  # noqa: E402
    latest_guarded_release,
    reset_demo,
    schedule,
    start_guarded_release,
    stop_guarded_release,
    targeting_url,
)

ROOT = Path(__file__).parent
PORT = int(os.environ.get("PORT", "8784"))
_ld_client: LDClient | None = None


def wait_for_ld(client: LDClient, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.is_initialized():
            return True
        time.sleep(0.05)
    return client.is_initialized()


def init_launchdarkly() -> None:
    global _ld_client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        return
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()
    wait_for_ld(_ld_client)


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        length = 0
    if length <= 0:
        return {}
    try:
        return json.loads(handler.rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def track_latency(username: str, latency_ms: object) -> tuple[int, dict]:
    """Record the slider value and one navigation for the logged-in user."""
    if _ld_client is None or not _ld_client.is_initialized():
        return 503, {"error": True, "detail": "LD_SDK_KEY is missing or the SDK did not initialize."}
    try:
        value = float(latency_ms)
    except (TypeError, ValueError):
        value = float("nan")
    if not str(username or "").strip() or not 0 <= value <= 500:
        return 400, {"error": True, "detail": "username and latencyMs (0–500) are required."}
    # LaunchDarkly: numeric custom event for the latency guardrail.
    # https://launchdarkly.com/docs/sdk/features/events
    return 200, track_observed(_ld_client, str(username).strip(), value)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        request_line = str(args[0])
        if request_line.startswith("GET /api/") or request_line.startswith("POST /api/track"):
            return
        super().log_message(fmt, *args)

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/highlight":
            username = (parse_qs(parsed.query).get("username") or [""])[0].strip()
            if not username:
                self._json({"error": "username query parameter is required"}, 400)
                return
            self._json(evaluate_highlight(_ld_client, username))
            return
        if parsed.path == "/api/release":
            self._json(latest_guarded_release())
            return
        if parsed.path == "/api/bootstrap":
            self._json({
                "flagKey": FLAG_HIGHLIGHT,
                "targetingUrl": targeting_url(),
                "schedule": schedule(),
                "thresholdMs": LATENCY_THRESHOLD_MS,
                "metrics": metric_views(),
            })
            return
        if parsed.path in ("/", "/index.html"):
            self._file(ROOT / "index.html", "text/html; charset=utf-8")
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/track":
            body = read_json(self)
            status, result = track_latency(body.get("username"), body.get("latencyMs"))
            self._json(result, status)
            return
        if parsed.path == "/api/release/start":
            # LaunchDarkly: start an environment release — guarded, three metrics.
            # https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release
            result = start_guarded_release()
        elif parsed.path == "/api/release/stop":
            # LaunchDarkly: stop an environment release — roll back to none.
            # https://launchdarkly.com/docs/api/environment-releases-beta/stop-an-environment-release
            result = stop_guarded_release()
        elif parsed.path == "/api/release/reset":
            # LaunchDarkly: turn the flag off so the demo returns to none.
            # https://launchdarkly.com/docs/api/feature-flags/update-feature-flag
            result = reset_demo()
        else:
            self.send_error(404)
            return
        status = 400 if result.get("error") or result.get("configured") is False else 200
        self._json(result, status)

    def _file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    init_launchdarkly()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Serving on http://127.0.0.1:{PORT}/", flush=True)
    try:
        server.serve_forever()
    finally:
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--evaluate-once":
        init_launchdarkly()
        try:
            print(json.dumps(evaluate_highlight(_ld_client, sys.argv[2])))
        finally:
            if _ld_client is not None:
                _ld_client.close()
        sys.exit(0)
    main()
