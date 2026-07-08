#!/usr/bin/env python3
"""Serve the guarded-rollout grid navigator web UI on a local HTTP server."""

import json
import os
import sys
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from highlight_eval import evaluate_highlight  # noqa: E402

ROOT = Path(__file__).parent
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


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/highlight":
            params = parse_qs(parsed.query)
            username = (params.get("username") or [""])[0].strip()
            if not username:
                self.send_error(400, "username query parameter is required")
                return
            body = json.dumps(evaluate_highlight(_ld_client, username)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main() -> None:
    init_launchdarkly()
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("", port), Handler)
    print(f"Serving on http://localhost:{port}/", flush=True)
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
