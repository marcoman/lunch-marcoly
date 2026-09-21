#!/usr/bin/env python3
"""Serve the static percentage-rollout grid navigator."""

from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rollout import evaluate_rollout, normalize_username  # noqa: E402

ROOT = Path(__file__).parent
_ld_client: LDClient | None = None


def init_launchdarkly() -> None:
    """Initialize one process-wide SDK client for percentage evaluation."""
    global _ld_client
    sdk_key = (os.environ.get("LD_SDK_KEY") or "").strip()
    if not sdk_key:
        print("Warning: LD_SDK_KEY not set — highlight defaults to none.", flush=True)
        return
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()
    if not _ld_client.is_initialized():
        print("Warning: LaunchDarkly SDK did not initialize.", flush=True)


def json_response(
    handler: SimpleHTTPRequestHandler, status: int, payload: object
) -> None:
    """Write a no-cache JSON response."""
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(SimpleHTTPRequestHandler):
    """Serve the UI and evaluate the rollout for the supplied username key."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/flags":
            params = parse_qs(parsed.query, keep_blank_values=True)
            try:
                username = normalize_username((params.get("username") or [""])[0])
                json_response(self, 200, evaluate_rollout(_ld_client, username))
            except ValueError as exc:
                json_response(self, 400, {"error": str(exc)})
            return
        if parsed.path == "/api/bootstrap":
            json_response(
                self,
                200,
                {
                    "appBanner": "16-percentage-rollout[python]",
                    "flagKey": "enable-grid-selection-highlight-pct",
                    "rollout": "30% green / 70% none",
                    "port": int(os.environ.get("PORT") or "8160"),
                },
            )
            return
        super().do_GET()


def main() -> None:
    """Start the web server and close the SDK during shutdown."""
    init_launchdarkly()
    port = int(os.environ.get("PORT") or "8160")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("16-percentage-rollout[python]")
    print(f"Open http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    main()
