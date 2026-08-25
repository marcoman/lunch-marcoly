# Reference Client Application Specification

This document defines the behavior of the **02-reference-client-code** application — the browser-side twin of [00-reference-code](../00-reference-code/application.md).

Navigation, login, and selection rules are **the same as 00**. The difference is *where the program runs*: the grid lives in the page. A local HTTP server only delivers static files.

Repository layout is in [project.md](../project.md). LaunchDarkly client SDK examples will live in a later **30-client-sdk** series; this example has **no LaunchDarkly**.

## Overview

A two-screen application implemented in **browser JavaScript**:

1. **Login** — collect a username (no password)
2. **Grid** — navigate a 3×3 grid with keyboard input

Selection is indicated by **`X` only** — no highlight colors.

Python, Java, and .NET may later host the same static page; they must not move evaluation into the server. The language that *decides* login, moves, and quit is JavaScript in the browser.

## Login screen

| Rule | Detail |
|------|--------|
| Fields | Username only — no password field |
| Validation | Username must be non-empty before continuing |
| On submit | Proceed to the grid screen; display the username in the grid header |

The username persists for the session until logout. Reloading the page returns to the login screen.

## Grid screen

### Grid layout

The main section is a **3×3 grid**:

| | Left (`l`) | Middle (`m`) | Right (`r`) |
|---|------------|--------------|-------------|
| **Top (`t`)** | `t/l` | `t/m` | `t/r` |
| **Middle (`m`)** | `m/l` | `m/m` | `m/r` |
| **Bottom (`b`)** | `b/l` | `b/m` | `b/r` |

Internally, positions use **row/column** abbreviations:

- Rows: `t` (top), `m` (middle), `b` (bottom)
- Columns: `l` (left), `m` (middle), `r` (right)
- Position notation: `{row}/{col}` — for example `t/l`, `m/m`, `b/r`

### Starting position

The cursor starts at **`m/m`** (center) when the grid screen first loads.

### Navigation

The user moves the selection with directional input:

| Input | Action |
|-------|--------|
| Up | Move one row toward `t` |
| Down | Move one row toward `b` |
| Left | Move one column toward `l` |
| Right | Move one column toward `r` |

**Edge behavior (default):** movement stops at the boundary. **Wrap-around is not permitted.**

| Current position | Press | Result |
|------------------|-------|--------|
| `t/l` | Up | `t/l` (unchanged) |
| `t/l` | Left | `t/l` (unchanged) |
| `t/r` | Right | `t/r` (unchanged) |
| `b/r` | Down | `b/r` (unchanged) |
| `t/l` | Right | `t/m` |
| `t/r` | Left | `t/m` |

A single move never jumps from one edge to the opposite edge (for example, `t/l` → `t/r` is impossible).

### Session control

While on the grid screen:

| Input | Action |
|-------|--------|
| `Q` or `q` | Quit the application |
| `L` or `l` | Log out — return to the login screen |

**Quit:** close the tab if the browser allows it; otherwise show that the application has closed.

**Logout:**

- Return to the login screen without exiting
- Clear the username field
- Reset grid state: current position `m/m`, previous position `—`
- The user may log in again with the same or a different username

### Screen layout

#### Header

| Field | Content |
|-------|---------|
| Name | Username from login |
| Current position | Selected cell in `{row}/{col}` notation (e.g. `m/m`) |
| Previous position | Position before the last move in `{row}/{col}` notation |

On the first render after login, **Previous position** is `—` (em dash) because no move has occurred yet.

After each successful move, **Previous position** updates to the position held before that move. Attempted moves at a boundary (no position change) do not update **Previous position**.

#### Main section

Renders the 3×3 grid. The selected cell is marked with an **`X`**. Unselected cells are empty.

## Presentation

- Default color scheme: **light mode**
- **No selection colors** — the selected cell is not highlighted with a background or border color
- **Unselected cells:** default (white or near-white) background, empty
- **Selected cell:** `X` centered in the cell on the same background as unselected cells

This baseline does **not** expose host OS, CPU model, or `/proc` attributes. Those belong to server-side 10-series examples. Browser-only attributes (for later client SDK demos) are out of scope here.

## Input mapping

| Platform | Up | Down | Left | Right | Log out | Quit |
|----------|----|------|------|-------|---------|------|
| Browser | ↑ or `w` | ↓ or `s` | ← or `a` | → or `d` | `L` or `l` | `Q` or `q` |

Arrow keys and WASD must work.

## State model

| State | Type | Notes |
|-------|------|-------|
| `username` | string | Set at login |
| `current` | position | `{row}/{col}` |
| `previous` | position \| null | `null` until first move; then last position before most recent move |

```text
position = { row: "t" | "m" | "b", col: "l" | "m" | "r" }
```

Display `previous` as `—` when null.

## Acceptance criteria

An implementation is correct when:

1. Login accepts a non-empty username and rejects an empty one
2. Grid starts at `m/m` with Previous position `—`
3. Arrow/WASD navigation moves one step per keypress with no wrap-around
4. Boundary keypresses leave the position unchanged and do not update Previous position
5. Header shows Name, Current position, and Previous position accurately after every change
6. Selected cell displays `X`; unselected cells do not
7. Selected cell has no background or border color highlight — `X` only on the default cell background
8. `Q` or `q` on the grid screen quits (or shows the closed state)
9. `L` or `l` on the grid screen returns to login with the username field cleared and grid state reset
10. Flag evaluation, SDK keys, and LaunchDarkly scripts are absent

## Further reading

- [00-reference-code/application.md](../00-reference-code/application.md) — same navigator on the server / console
- [project.md](../project.md) — repository layout and conventions
- [README.md](README.md) — example overview
