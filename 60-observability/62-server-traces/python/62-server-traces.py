#!/usr/bin/env python3
"""Serve the grid navigator with LaunchDarkly login and move traces."""

from __future__ import annotations

import json
import os
import threading
import uuid
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# =============================================================================
# BEGIN LAUNCHDARKLY OBSERVABILITY: plugin and tracing imports
#
# ObservabilityPlugin connects the Python server SDK to LaunchDarkly
# Observability. `observe` provides the manual span API used below.
# https://launchdarkly.com/docs/sdk/observability/python
# =============================================================================
import ldclient
from ldclient.config import Config
from ldobserve import ObservabilityConfig, ObservabilityPlugin, observe
# =============================================================================
# END LAUNCHDARKLY OBSERVABILITY: plugin and tracing imports
# =============================================================================

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")
DIRECTIONS = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1),
}


def new_state() -> dict[str, Any]:
    """Return a logged-out navigator at the canonical center position."""
    return {"username": "", "row": 1, "col": 1, "previous": None}


class SessionStore:
    """Keep small demo sessions in memory; restarting the process clears them."""

    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            return self._states.setdefault(session_id, new_state())

    def update(self, session_id: str, action) -> Any:
        with self._lock:
            return action(self._states.setdefault(session_id, new_state()))


SESSIONS = SessionStore()


def apply_login(state: dict[str, Any], username: str) -> None:
    """Reset the session and record who logged in."""
    # =========================================================================
    # BEGIN LAUNCHDARKLY OBSERVABILITY: successful-login span
    #
    # Record the username on this demo span so Traces can show who started the
    # session. Empty-username failures never reach this function.
    # https://launchdarkly.com/docs/sdk/features/observability-traces#python
    # =========================================================================
    with observe.start_span(
        "grid.login",
        attributes={"grid.username": username},
    ):
        state.update(new_state())
        state["username"] = username
    # =========================================================================
    # END LAUNCHDARKLY OBSERVABILITY: successful-login span
    # =========================================================================


def public_state(state: dict[str, Any], *, moved: bool | None = None) -> dict[str, Any]:
    """Serialize internal row/column indexes into the browser-facing contract."""
    result: dict[str, Any] = {
        "loggedIn": bool(state["username"]),
        "username": state["username"],
        "current": f"{ROWS[state['row']]}/{COLS[state['col']]}",
        "previous": state["previous"],
    }
    if moved is not None:
        result["moved"] = moved
    return result


def apply_move(state: dict[str, Any], direction: str) -> bool:
    """Move one cell and trace it only when the position actually changes."""
    dr, dc = DIRECTIONS[direction]
    old_row, old_col = state["row"], state["col"]
    new_row = max(0, min(2, old_row + dr))
    new_col = max(0, min(2, old_col + dc))
    if (new_row, new_col) == (old_row, old_col):
        return False

    old_position = f"{ROWS[old_row]}/{COLS[old_col]}"
    new_position = f"{ROWS[new_row]}/{COLS[new_col]}"

    # =========================================================================
    # BEGIN LAUNCHDARKLY OBSERVABILITY: successful-move span
    #
    # `start_span` is a context manager: leaving this block ends and exports the
    # span. Safe, low-cardinality attributes explain the move without recording
    # the username or other potentially sensitive data.
    # https://launchdarkly.com/docs/sdk/features/observability-traces#python
    # =========================================================================
    with observe.start_span(
        "grid.move",
        attributes={
            "grid.direction": direction,
            "grid.from": old_position,
            "grid.to": new_position,
        },
    ):
        state["previous"] = old_position
        state["row"], state["col"] = new_row, new_col
    # =========================================================================
    # END LAUNCHDARKLY OBSERVABILITY: successful-move span
    # =========================================================================

    return True


class Handler(SimpleHTTPRequestHandler):
    """Serve the UI and the session-backed navigator API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/state":
            session_id, is_new = self._session()
            self._json(200, public_state(SESSIONS.get(session_id)), session_id if is_new else None)
            return
        super().do_GET()

    def do_POST(self) -> None:
        session_id, is_new = self._session()
        try:
            body = self._read_json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"error": "Request body must be valid JSON."}, session_id if is_new else None)
            return

        if self.path == "/api/login":
            username = str(body.get("username", "")).strip()
            if not username:
                self._json(400, {"error": "Username is required."}, session_id if is_new else None)
                return

            SESSIONS.update(session_id, lambda state: apply_login(state, username))
            self._json(200, public_state(SESSIONS.get(session_id)), session_id if is_new else None)
            return

        if self.path == "/api/logout":
            SESSIONS.update(session_id, lambda state: state.update(new_state()))
            self._json(200, public_state(SESSIONS.get(session_id)), session_id if is_new else None)
            return

        if self.path == "/api/move":
            direction = str(body.get("direction", "")).lower()
            if direction not in DIRECTIONS:
                self._json(400, {"error": "Direction must be up, down, left, or right."})
                return
            if not SESSIONS.get(session_id)["username"]:
                self._json(409, {"error": "Log in before moving."})
                return
            moved = SESSIONS.update(session_id, lambda state: apply_move(state, direction))
            self._json(200, public_state(SESSIONS.get(session_id), moved=moved))
            return

        self._json(404, {"error": "Not found."})

    def _session(self) -> tuple[str, bool]:
        jar = cookies.SimpleCookie(self.headers.get("Cookie"))
        morsel = jar.get("grid_session")
        if morsel and morsel.value:
            return morsel.value, False
        return uuid.uuid4().hex, True

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise json.JSONDecodeError("Expected object", "", 0)
        return value

    def _json(
        self,
        status: int,
        payload: dict[str, Any],
        session_id: str | None = None,
    ) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        if session_id:
            self.send_header("Set-Cookie", f"grid_session={session_id}; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()
        self.wfile.write(encoded)


# =============================================================================
# BEGIN LAUNCHDARKLY OBSERVABILITY: initialize SDK and plugin
#
# The plugin config names the OpenTelemetry service shown in LaunchDarkly.
# Config.plugins attaches it to the process-wide LaunchDarkly server SDK client.
# This example uses the SDK for observability only; it evaluates no flags.
# https://launchdarkly.com/docs/sdk/observability/python
# =============================================================================
def initialize_observability() -> ldclient.LDClient:
    """Initialize the process-wide SDK client and observability exporter."""
    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    if not sdk_key:
        raise RuntimeError(
            "LD_SDK_KEY is required. Export an environment server-side SDK key."
        )

    plugin = ObservabilityPlugin(
        ObservabilityConfig(
            service_name="lunch-marcoly-62-server-traces",
            service_version=os.environ.get("SERVICE_VERSION", "development"),
        )
    )
    ldclient.set_config(Config(sdk_key=sdk_key, plugins=[plugin]))
    return ldclient.get()
# =============================================================================
# END LAUNCHDARKLY OBSERVABILITY: initialize SDK and plugin
# =============================================================================


def main() -> None:
    """Initialize observability, then run the local server until interrupted."""
    client = initialize_observability()
    port = int(os.environ.get("PORT") or "8620")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"62-server-traces running at http://127.0.0.1:{port}/")
    print("Login and successful moves create spans. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

        # =====================================================================
        # BEGIN LAUNCHDARKLY OBSERVABILITY: graceful shutdown
        #
        # Close the SDK so queued observability data can flush before exit.
        # https://launchdarkly.com/docs/sdk/server-side/python#shut-down-the-client
        # =====================================================================
        client.close()
        # =====================================================================
        # END LAUNCHDARKLY OBSERVABILITY: graceful shutdown
        # =====================================================================


if __name__ == "__main__":
    main()
