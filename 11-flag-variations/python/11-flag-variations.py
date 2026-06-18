#!/usr/bin/env python3
"""Serve the flag-variations grid navigator web UI on a local HTTP server."""

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
from flag_variations import evaluate_flags as eval_flags  # noqa: E402
from host_os import HOST_OS_ATTR, detect_host_os  # noqa: E402

ROOT = Path(__file__).parent
_ld_client: LDClient | None = None
_host_os = detect_host_os()


def init_launchdarkly() -> None:
    global _ld_client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        print("Warning: LD_SDK_KEY not set — flags use defaults.", flush=True)
        return
    ldclient.set_config(Config(sdk_key, private_attributes=[HOST_OS_ATTR]))
    _ld_client = ldclient.get()
    if not _ld_client.is_initialized():
        print("Warning: LaunchDarkly SDK did not initialize — flags use defaults.", flush=True)


class Handler(SimpleHTTPRequestHandler):
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
            body = json.dumps(eval_flags(_ld_client, username, _host_os)).encode("utf-8")
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
    main()
