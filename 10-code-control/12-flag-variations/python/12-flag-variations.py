#!/usr/bin/env python3
"""Serve the flag-variations grid navigator web UI on a local HTTP server."""

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
from flag_variations import evaluate_flags as eval_flags  # noqa: E402
from host_os import (  # noqa: E402
    ANONYMOUS_CONTEXT_KEY,
    FLAG_ANON_OS_EMOJI,
    HOST_OS_ATTR,
    detect_host_os,
)
from ld_flag_controls import (  # noqa: E402
    api_config,
    apply_flag_control,
    list_flag_controls,
)

# LaunchDarkly: multivariate evaluation (string / number / JSON) + anonymous boolean
# https://launchdarkly.com/docs/sdk/features/flag-types
# In-app Controls use the REST API (not the SDK).
# https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag

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


def evaluate_flags(username: str) -> dict:
    """Evaluate flags and attach LD context info for the lab Context tab."""
    response = eval_flags(_ld_client, username, _host_os)
    response["ldContext"] = {
        "user": {
            "kind": "user",
            "key": username,
            "note": "String, number, and JSON flags evaluate against this user context.",
        },
        "anonymous": {
            "kind": "user",
            "key": ANONYMOUS_CONTEXT_KEY,
            "anonymous": True,
            "attributes": {HOST_OS_ATTR: _host_os},
            "privateAttributes": [HOST_OS_ATTR],
            "flagKey": FLAG_ANON_OS_EMOJI,
            "note": (
                f"{FLAG_ANON_OS_EMOJI} uses this anonymous context. "
                f"{HOST_OS_ATTR} is private (targeting only; redacted from analytics)."
            ),
        },
    }
    return response


def _json_response(handler: SimpleHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or "0")
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        data = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object")
    return data


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
            _json_response(self, 200, evaluate_flags(username))
            return

        if parsed.path == "/api/flag-controls":
            _json_response(self, 200, list_flag_controls())
            return

        if parsed.path == "/api/bootstrap":
            _json_response(
                self,
                200,
                {
                    "appBanner": "12-flag-variations[python]",
                    "hostOs": _host_os,
                    "controls": api_config(),
                },
            )
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/flag-controls":
            self.send_error(404, "Not found")
            return
        try:
            data = _read_json(self)
            key = str(data.get("key") or "").strip()
            if not key:
                raise ValueError('"key" is required')
            turn_on: bool | None = bool(data["on"]) if "on" in data else None
            fallthrough = data["fallthrough"] if "fallthrough" in data else None
            result = apply_flag_control(key, turn_on=turn_on, fallthrough=fallthrough)
            _json_response(self, 200, result)
        except ValueError as exc:
            _json_response(self, 400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            _json_response(self, 502, {"ok": False, "error": str(exc)})


def main() -> None:
    init_launchdarkly()
    cfg = api_config()
    if cfg["configured"]:
        print(
            f"Flag controls ready (project={cfg['projectKey']} env={cfg['environmentKey']})",
            flush=True,
        )
    else:
        print(
            "Warning: flag Controls disabled — missing " + ", ".join(cfg["missing"]),
            flush=True,
        )

    # PORT override: solo default 8080; series portal typically uses 8120.
    port = int(os.environ.get("PORT") or "8080")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Grid navigator (flag variations) running at http://127.0.0.1:{port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    finally:
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    main()
