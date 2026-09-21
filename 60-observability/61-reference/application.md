# 61-reference application specification

This is the [00-reference-code grid navigator](../../00-reference-code/application.md)
with one architectural change: Python owns session state.

## Behavior

- Login requires a non-empty username.
- The 3×3 grid starts at `m/m`; previous position starts as `—`.
- Arrow keys and WASD move one cell without wrap-around.
- A blocked edge move does not change the previous position.
- `L` logs out and resets state. `Q` closes the browser application view.
- Selection remains an uncolored `X`.

## Server contract

The browser keeps a session cookie and calls:

| Request | Purpose |
|---------|---------|
| `GET /api/state` | Read the current session state |
| `POST /api/login` with `{"username":"..."}` | Log in and reset the grid |
| `POST /api/move` with `{"direction":"up|down|left|right"}` | Attempt one move |
| `POST /api/logout` | Clear the session state |

Responses are JSON. State includes `loggedIn`, `username`, `current`,
`previous`, and—on moves—`moved`.

## Why this baseline exists

The Python implementation of `00-reference-code` only serves static files; its
grid logic runs entirely in the browser. This server-owned twin creates an
honest operation for `62-server-traces` to instrument. It contains no
LaunchDarkly code.
