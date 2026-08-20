#!/usr/bin/env python3
"""Serve the flag-enabled grid navigator web UI on a local HTTP server."""

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from highlight_style import (  # noqa: E402
    FLAG_CONTEXT,
    FLAG_COUNT,
    FLAG_HIGHLIGHT,
    build_flag_response,
)
from host_os import (  # noqa: E402
    FLAG_OS_EMOJI,
    HOST_OS_ATTR,
    build_evaluation_context,
    detect_host_os,
)

# LaunchDarkly capability: Boolean flag evaluation (server-side SDK)
# Private attribute hostOs is set on the evaluation context for targeting.
# See: https://launchdarkly.com/docs/sdk/features/private-attributes

ROOT = Path(__file__).parent
_ld_client: LDClient | None = None
_host_os = detect_host_os()


def init_launchdarkly() -> None:
    """Initialize the server-side SDK from LD_SDK_KEY."""
    global _ld_client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        print("Warning: LD_SDK_KEY not set — flags default to off.", flush=True)
        return
    ldclient.set_config(Config(sdk_key, private_attributes=[HOST_OS_ATTR]))
    _ld_client = ldclient.get()
    if not _ld_client.is_initialized():
        print("Warning: LaunchDarkly SDK did not initialize — flags default to off.", flush=True)


def evaluate_flags(username: str) -> dict[str, object]:
    """Return current flag values and resolved highlight styling for a user context."""
    if _ld_client is None or not _ld_client.is_initialized():
        return build_flag_response(username, False, False, False, False, _host_os)
    context, host_os = build_evaluation_context(username)
    highlight = bool(_ld_client.variation(FLAG_HIGHLIGHT, context, False))
    context_highlight = bool(_ld_client.variation(FLAG_CONTEXT, context, False))
    show_count = bool(_ld_client.variation(FLAG_COUNT, context, False))
    show_os_emoji = bool(_ld_client.variation(FLAG_OS_EMOJI, context, False))
    return build_flag_response(
        username, highlight, context_highlight, show_count, show_os_emoji, host_os
    )


class Handler(SimpleHTTPRequestHandler):
    """Serve static files and the /api/flags evaluation endpoint."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/flags":
            params = parse_qs(parsed.query)
            username = (params.get("username") or [""])[0].strip()
            if not username:
                self.send_error(400, "username query parameter is required")
                return
            body = json.dumps(evaluate_flags(username)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main() -> None:
    init_launchdarkly()
    port = 8080
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"Grid navigator (flag enablement) running at http://127.0.0.1:{port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    finally:
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    main()
