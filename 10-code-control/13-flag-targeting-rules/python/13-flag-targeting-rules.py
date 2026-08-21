#!/usr/bin/env python3
"""Serve the team-targeting grid navigator and LaunchDarkly lab."""

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
from ld_flag_controls import api_config, apply_flag_control, list_flag_controls  # noqa: E402
from team_style import evaluate_team_style, normalize_team  # noqa: E402

# LaunchDarkly: targeting rules inspect the public team context attribute.
# https://launchdarkly.com/docs/home/flags/target-rules

ROOT = Path(__file__).parent
_ld_client: LDClient | None = None


def init_launchdarkly() -> None:
    """Initialize the SDK without private attributes; team stays public."""
    global _ld_client
    sdk_key = (os.environ.get("LD_SDK_KEY") or "").strip()
    if not sdk_key:
        print("Warning: LD_SDK_KEY not set — flag uses plain default.", flush=True)
        return
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()
    if not _ld_client.is_initialized():
        print("Warning: LaunchDarkly SDK did not initialize.", flush=True)


def _json_response(handler: SimpleHTTPRequestHandler, status: int, payload: object) -> None:
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
    """Serve static UI files and the evaluation/control APIs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/flags":
            params = parse_qs(parsed.query, keep_blank_values=True)
            username = (params.get("username") or [""])[0].strip()
            if not username:
                _json_response(self, 400, {"error": "username query parameter is required"})
                return
            try:
                team = normalize_team((params.get("team") or [""])[0])
            except ValueError as exc:
                _json_response(self, 400, {"error": str(exc)})
                return
            _json_response(self, 200, evaluate_team_style(_ld_client, username, team))
            return
        if parsed.path == "/api/bootstrap":
            _json_response(self, 200, {
                "appBanner": "13-flag-targeting-rules[python]",
                "controls": api_config(),
            })
            return
        if parsed.path == "/api/flag-controls":
            try:
                _json_response(self, 200, list_flag_controls())
            except Exception as exc:  # noqa: BLE001
                _json_response(self, 502, {"configured": True, "flags": [], "error": str(exc)})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/flag-controls":
            self.send_error(404, "Not found")
            return
        try:
            data = _read_json(self)
            key = str(data.get("key") or "").strip()
            if not key:
                raise ValueError('"key" is required')
            result = apply_flag_control(
                key,
                turn_on=bool(data["on"]) if "on" in data else None,
                fallthrough=data.get("fallthrough") if "fallthrough" in data else None,
            )
            _json_response(self, 200, result)
        except ValueError as exc:
            _json_response(self, 400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            _json_response(self, 502, {"ok": False, "error": str(exc)})


def main() -> None:
    """Start the local web server and close the SDK cleanly on shutdown."""
    init_launchdarkly()
    port = int(os.environ.get("PORT") or "8080")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Targeting-rules lab running at http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    finally:
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    main()
