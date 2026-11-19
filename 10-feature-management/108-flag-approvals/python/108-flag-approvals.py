#!/usr/bin/env python3
"""Serve the approval lab for the move-count flag.

The grid hides Count until the flag is on. Turning it on goes through an
approval request. The page does not patch targeting itself.

Approvals
https://launchdarkly.com/docs/home/releases/approvals
"""

from __future__ import annotations

import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import ldclient
from ldclient import Config
from ldclient import Context
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from approvals import (  # noqa: E402
    FLAG_KEY,
    ApprovalError,
    api_config,
    apply_approval,
    approval_state,
    request_approval,
    reset_demo,
)

ROOT = Path(__file__).parent
_ld_client: LDClient | None = None


def init_launchdarkly() -> None:
    """Start the server SDK used to read the move-count flag.

    LaunchDarkly: server-side Python SDK · boolean variation
    https://launchdarkly.com/docs/sdk/server-side/python
    """
    global _ld_client
    sdk_key = (os.environ.get("LD_SDK_KEY") or "").strip()
    if not sdk_key:
        print("Warning: LD_SDK_KEY not set — the count stays hidden.", flush=True)
        return
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()
    if not _ld_client.is_initialized():
        print("Warning: LaunchDarkly SDK did not initialize.", flush=True)


def evaluate_count(username: str) -> dict[str, object]:
    """Read the one flag. The default is hidden.

    LaunchDarkly: boolean variation · evaluation reasons
    https://launchdarkly.com/docs/home/flags/boolean
    """
    username = username.strip()
    if not username:
        raise ValueError("Username is required")
    if _ld_client is None or not _ld_client.is_initialized():
        return {
            "username": username,
            "flagKey": FLAG_KEY,
            "showMoveCount": False,
            "reason": "DEFAULT",
            "sdk": False,
        }
    context = Context.builder(username).kind("user").name(username).build()
    detail = _ld_client.variation_detail(FLAG_KEY, context, False)
    reason = getattr(detail, "reason", None)
    if isinstance(reason, dict):
        kind = str(reason.get("kind", "UNKNOWN"))
    else:
        kind = str(getattr(reason, "kind", None) or "UNKNOWN")
    return {
        "username": username,
        "flagKey": FLAG_KEY,
        "showMoveCount": bool(detail.value),
        "reason": kind,
        "sdk": True,
    }


def _json(handler: SimpleHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or "0")
    try:
        value = json.loads(handler.rfile.read(length).decode() or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("Request body must be a JSON object")
    return value


class Handler(SimpleHTTPRequestHandler):
    """Serve the grid and the approval rail."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/flags":
            params = parse_qs(parsed.query, keep_blank_values=True)
            try:
                username = (params.get("username") or [""])[0]
                _json(self, 200, evaluate_count(username))
            except ValueError as exc:
                _json(self, 400, {"error": str(exc)})
            return
        if parsed.path == "/api/approval":
            try:
                _json(self, 200, approval_state())
            except RuntimeError as exc:
                _json(self, 502, {"ok": False, **api_config(), "request": None, "error": str(exc)})
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = _read_json(self)
            if path == "/api/approval":
                _json(self, 200, request_approval())
                return
            if path == "/api/approval/apply":
                _json(self, 200, apply_approval(str(body.get("id") or "")))
                return
            if path == "/api/approval/reset":
                _json(self, 200, reset_demo())
                return
        except ValueError as exc:
            _json(self, 400, {"ok": False, "error": str(exc)})
            return
        except ApprovalError as exc:
            _json(self, 502, {"ok": False, "error": str(exc), "steps": exc.steps, "request": None})
            return
        except RuntimeError as exc:
            _json(self, 502, {"ok": False, "error": str(exc)})
            return
        self.send_error(404, "Not found")

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> None:
    """Start the lab on :8180 unless PORT is set."""
    init_launchdarkly()
    port = int(os.environ.get("PORT") or "8180")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("108-flag-approvals[python]", flush=True)
    print(f"Open http://127.0.0.1:{port}/", flush=True)
    try:
        server.serve_forever()
    finally:
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    main()
