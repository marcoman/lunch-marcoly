#!/usr/bin/env python3
"""Serve the API progressive-rollout grid.

This process evaluates the flag. Start progressive release POSTs the
environment release. /api/release reads it back for the drawer.

LaunchDarkly: string variation, plus list environment releases
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
from highlight_eval import evaluate_highlight  # noqa: E402
from release_status import (  # noqa: E402
    latest_progressive_release,
    schedule,
    reset_demo,
    start_progressive_release,
    stop_progressive_release,
    targeting_url,
)

ROOT = Path(__file__).parent
PORT = int(os.environ.get("PORT", "8780"))
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


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        request_line = str(args[0])
        if request_line.startswith("GET /api/") or request_line.startswith("POST /api/release "):
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
            self._json(latest_progressive_release())
            return
        if parsed.path == "/api/bootstrap":
            self._json({
                "flagKey": "api-progressive-grid-highlight",
                "targetingUrl": targeting_url(),
                "schedule": schedule(),
            })
            return
        if parsed.path in ("/", "/index.html"):
            self._file(ROOT / "index.html", "text/html; charset=utf-8")
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/release/start":
            # LaunchDarkly: start an environment release — progressive, no metrics.
            # https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release
            result = start_progressive_release()
        elif parsed.path == "/api/release/stop":
            # LaunchDarkly: stop an environment release — roll back to none.
            # https://launchdarkly.com/docs/api/environment-releases-beta/stop-an-environment-release
            result = stop_progressive_release()
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
