#!/usr/bin/env python3
"""Serve the ABCD test grid navigator web UI on a local HTTP server."""

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from abcd_eval import close_client, evaluate_count_label, init_client  # noqa: E402

ROOT = Path(__file__).parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/count-label":
            params = parse_qs(parsed.query)
            username = (params.get("username") or [""])[0].strip()
            if not username:
                self.send_error(400, "username query parameter is required")
                return
            body = json.dumps({"countLabel": evaluate_count_label(username)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def main() -> None:
    init_client()
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("", port), Handler)
    print(f"Serving on http://localhost:{port}/", flush=True)
    try:
        server.serve_forever()
    finally:
        close_client()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--evaluate-once":
        init_client()
        try:
            print(evaluate_count_label(sys.argv[2]))
        finally:
            close_client()
        sys.exit(0)

    main()
