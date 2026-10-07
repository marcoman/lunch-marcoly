#!/usr/bin/env python3
"""
04-terraform-codegen.py — HTTP adapter for the Terraform codegen screen.

GET  /              → index.html
GET  /api/bootstrap → config key and the models the process can run
POST /api/generate  → SSE. Body {"models": ["local-1b", ...]}. Selected models run in order.

LaunchDarkly work lives in agent_core.py.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agent_core import (  # noqa: E402
    available_generators,
    config_key,
    generate_stream,
    init_launchdarkly,
)

APP_BANNER = "04-terraform-codegen[python]"
PORT = 8740


class Handler(BaseHTTPRequestHandler):
    server_version = "TerraformCodegenHTTP/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._serve_file(HERE / "index.html", "text/html; charset=utf-8")
            return
        if path == "/api/bootstrap":
            self._json(
                200,
                {
                    "appBanner": APP_BANNER,
                    "configKey": config_key(),
                    "generators": [
                        {
                            "id": spec["id"],
                            "model": spec["model_name"],
                            "contextKey": spec["context_key"],
                            "provider": spec.get("provider", "ollama"),
                            "note": spec.get("note", ""),
                            "enabled": spec.get("enabled", True),
                        }
                        for spec in available_generators()
                    ],
                },
            )
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/generate":
            self.send_error(404, "Not found")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            body = {}
        selected = body.get("models") if isinstance(body, dict) else None
        if selected is not None and not isinstance(selected, list):
            selected = None
        ids = [str(item) for item in selected] if selected else None
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            for event in generate_stream(ids):
                payload = json.dumps(event, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
        except BrokenPipeError:
            return

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(404, "Not found")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    init_launchdarkly()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(APP_BANNER)
    print(f"Open http://127.0.0.1:{PORT}/")
    print(f"LD_AGENT_CONFIG_KEY={config_key()}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
