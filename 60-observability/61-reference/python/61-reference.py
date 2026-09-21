#!/usr/bin/env python3
"""Serve the server-owned grid navigator baseline on port 8610."""

from __future__ import annotations

import json
import os
import threading
import uuid
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

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
    """Move one cell without wrap-around; return whether position changed."""
    dr, dc = DIRECTIONS[direction]
    old_row, old_col = state["row"], state["col"]
    new_row = max(0, min(2, old_row + dr))
    new_col = max(0, min(2, old_col + dc))
    if (new_row, new_col) == (old_row, old_col):
        return False
    state["previous"] = f"{ROWS[old_row]}/{COLS[old_col]}"
    state["row"], state["col"] = new_row, new_col
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

            def login(state: dict[str, Any]) -> None:
                state.update(new_state())
                state["username"] = username

            SESSIONS.update(session_id, login)
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


def main() -> None:
    """Run the local threaded web server until interrupted."""
    port = int(os.environ.get("PORT") or "8610")
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"61-reference running at http://127.0.0.1:{port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
