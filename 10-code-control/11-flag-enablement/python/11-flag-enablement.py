#!/usr/bin/env python3
"""Serve the flag-enabled grid navigator web UI on a local HTTP server."""

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
from highlight_style import (  # noqa: E402
    FLAG_CONTEXT,
    FLAG_COUNT,
    FLAG_HIGHLIGHT,
    build_flag_response,
    interpret_highlight_variation,
    parse_cohorts,
)
from host_os import (  # noqa: E402
    FLAG_OS_EMOJI,
    HOST_OS_ATTR,
    build_evaluation_context,
    detect_host_os,
)
from ld_flag_controls import (  # noqa: E402
    api_config,
    apply_flag_control,
    list_flag_controls,
)

# LaunchDarkly capability: Boolean flag evaluation (server-side SDK)
# Private attribute hostOs is set on the evaluation context for targeting.
# See: https://launchdarkly.com/docs/sdk/features/private-attributes
#
# In-app Controls use the REST API (turnFlagOn / turnFlagOff) — not the SDK.
# https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag

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
    """Return current flag values, styling, and the LD evaluation context for the UI."""
    # LaunchDarkly: contexts — key + attributes used at evaluation time
    # https://launchdarkly.com/docs/home/flags/contexts
    if _ld_client is None or not _ld_client.is_initialized():
        host_os = _host_os
        response = build_flag_response(username, False, False, False, False, host_os)
    else:
        context, host_os = build_evaluation_context(username)
        # Highlight may be boolean or string ("none" / color) depending on the project flag.
        highlight_raw = _ld_client.variation(FLAG_HIGHLIGHT, context, False)
        highlight, served_color = interpret_highlight_variation(highlight_raw)
        context_highlight = bool(_ld_client.variation(FLAG_CONTEXT, context, False))
        show_count = bool(_ld_client.variation(FLAG_COUNT, context, False))
        show_os_emoji = bool(_ld_client.variation(FLAG_OS_EMOJI, context, False))
        response = build_flag_response(
            username,
            highlight,
            context_highlight,
            show_count,
            show_os_emoji,
            host_os,
            served_color,
        )

    is_human, is_robot, is_beta = parse_cohorts(username)
    response["ldContext"] = {
        "kind": "user",
        "key": username,
        "attributes": {
            HOST_OS_ATTR: host_os,
        },
        "privateAttributes": [HOST_OS_ATTR],
        "appDerived": {
            "cohortWords": {
                "human": is_human,
                "robot": is_robot,
                "beta": is_beta,
            },
            "note": (
                "Cohort words are parsed in app code from the username for the "
                "context-highlight flag — they are not separate LD context attributes."
            ),
        },
        "note": (
            f"{HOST_OS_ATTR} is a private attribute: used for targeting, "
            "redacted from analytics events sent to LaunchDarkly."
        ),
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
    """Serve static files, flag evaluation, and REST-backed flag controls."""

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
            # LaunchDarkly: REST get feature flag (env-filtered status)
            _json_response(self, 200, list_flag_controls())
            return

        if parsed.path == "/api/bootstrap":
            _json_response(
                self,
                200,
                {
                    "appBanner": "11-flag-enablement[python]",
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
            turn_on: bool | None
            if "on" in data:
                turn_on = bool(data["on"])
            else:
                turn_on = None
            fallthrough = data.get("fallthrough")
            fallthrough_value = (
                str(fallthrough).strip() if fallthrough is not None else None
            ) or None
            result = apply_flag_control(
                key, turn_on=turn_on, fallthrough_value=fallthrough_value
            )
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
            "Warning: flag Controls disabled — missing "
            + ", ".join(cfg["missing"]),
            flush=True,
        )

    # PORT override: solo default 8080; series portal spawns this on 8110.
    port = int(os.environ.get("PORT") or "8080")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Grid navigator (flag enablement) running at http://127.0.0.1:{port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    finally:
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    main()
