#!/usr/bin/env python3
"""Serve the first presentation of 24-multitenant-datacenter.

The floor and the rolling deployments live in the page. The Flags tab writes
targeting rules. A clicked size row is evaluated as one multi-context.

LaunchDarkly: multi-context, one evaluation per size row.
https://launchdarkly.com/docs/home/flags/multi-contexts
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXAMPLE))

from flags_api import apply_control, close_sdk, evaluate_context, snapshot  # noqa: E402
from floor import floor_payload  # noqa: E402

PORT = int(os.environ.get("PORT", "8788"))
INDEX = Path(__file__).resolve().parent / "index.html"
APP_BANNER = "24-multitenant-datacenter[python]"


def safe_icon(url_path: str) -> Path | None:
    """Serve an icon from this example. A path that leaves the folder is ignored."""
    if not (url_path.startswith("/icons/") or url_path.startswith("/customizations/")):
        return None
    relative = Path(url_path.lstrip("/"))
    if ".." in relative.parts:
        return None
    path = (EXAMPLE / relative).resolve()
    root = EXAMPLE.resolve()
    if path != root and root not in path.parents:
        return None
    if path.is_file():
        return path
    return None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            body = INDEX.read_bytes()
            self._send(200, "text/html; charset=utf-8", body)
            return
        if path == "/api/floor":
            payload = floor_payload()
            payload["banner"] = APP_BANNER
            self._send(200, "application/json", json.dumps(payload).encode())
            return
        if path == "/api/flags":
            try:
                self._json(snapshot())
            except RuntimeError as exc:
                self._json({"ok": False, "configured": False, "missing": [], "flags": [], "error": str(exc)})
            return
        icon = safe_icon(path)
        if icon is not None:
            kind = "image/svg+xml" if icon.suffix == ".svg" else "application/octet-stream"
            self._send(200, kind, icon.read_bytes())
            return
        self._send(404, "text/plain; charset=utf-8", b"Not found")

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            self._json({"ok": False, "error": "Invalid JSON"}, 400)
            return
        try:
            if path == "/api/flags":
                self._json(apply_control(body))
                return
            if path == "/api/evaluate":
                self._json(evaluate_context(body))
                return
        except (RuntimeError, ValueError) as exc:
            self._json({"ok": False, "configured": False, "error": str(exc)}, 400)
            return
        self._send(404, "text/plain; charset=utf-8", b"Not found")

    def _json(self, body: dict, status: int = 200) -> None:
        self._send(status, "application/json", json.dumps(body).encode())

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(APP_BANNER, flush=True)
    print(f"Open http://127.0.0.1:{PORT}/", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        close_sdk()
        server.server_close()


if __name__ == "__main__":
    main()
