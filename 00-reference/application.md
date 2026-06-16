# Reference Application Specification

This document defines the behavior of the **00-reference** application — a simple grid navigator used as the canonical example every language implementation must match.

Repository layout and README format are in [project.md](../project.md). Feature flag behavior is in [10-flag-enablement/application.md](../10-flag-enablement/application.md).

## Overview

A two-screen application:

1. **Login** — collect a username (no password)
2. **Grid** — navigate a 3×3 grid with keyboard input

All implementations must produce equivalent behavior. Differences are limited to platform-appropriate presentation (terminal box drawing vs browser layout). Selection is indicated by **`X` only** — no highlight colors.

## Login screen

| Rule | Detail |
|------|--------|
| Fields | Username only — no password field |
| Validation | Username must be non-empty before continuing |
| On submit | Proceed to the grid screen; display the username in the grid header |

The username persists for the session until logout. Re-launching the application returns to the login screen.

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

**Quit:** the application exits (console) or closes (web; if the browser blocks closing the tab, show that the application has closed).

**Logout:**

- Return to the login screen without exiting
- Clear the username field
- Reset grid state: current position `m/m`, previous position `—`
- The user may log in again with the same or a different username

### Screen layout

The grid screen has two sections:

#### Header

Displays three fields:

| Field | Content |
|-------|---------|
| Name | Username from login |
| Current position | Selected cell in `{row}/{col}` notation (e.g. `m/m`) |
| Previous position | Position before the last move in `{row}/{col}` notation |

On the first render after login, **Previous position** is `—` (em dash) because no move has occurred yet.

After each successful move, **Previous position** updates to the position held before that move. Attempted moves at a boundary (no position change) do not update **Previous position**.

#### Main section

Renders the 3×3 grid. The selected cell is marked with an **`X`**.

Unselected cells are empty (no marker).

Example at `m/m`:

```
┌───┬───┬───┐
│   │   │   │
├───┼───┼───┤
│   │ X │   │
├───┼───┼───┤
│   │   │   │
└───┴───┴───┘
```

(Exact borders and spacing may vary by platform; cell contents and selection state must not.)

## Presentation

### Console applications

Directories: `python-console/`, `node-console/`, `java-console/`, `cpp/`, `go/`, `rust/`

- **No colors** — do not use ANSI color codes or terminal color pairs for selection
- **Selected cell:** `X` inside the cell (heavy box characters such as `┏━━━┓` / `┃ X ┃` / `┗━━━┛` are acceptable for layout; they must not be colored)
- **Unselected cells:** empty (no marker), default terminal styling
- Header fields use default terminal styling

### Web applications

Directories: `python/`, `node/`, `java/`

- Default color scheme: **light mode**
- **No selection colors** — the selected cell is not highlighted with a background or border color
- **Unselected cells:** default (white or near-white) background, empty
- **Selected cell:** `X` centered in the cell on the same background as unselected cells
- Header: readable contrast against the page background (page chrome may use neutral text colors; the grid selection itself has no highlight color)

## Input mapping

| Platform | Up | Down | Left | Right | Log out | Quit |
|----------|----|------|------|-------|---------|------|
| Console | ↑ or `w` | ↓ or `s` | ← or `a` | → or `d` | `L` or `l` | `Q` or `q` |
| Web | ↑ or `w` | ↓ or `s` | ← or `a` | → or `d` | `L` or `l` | `Q` or `q` |

Implementations may support additional aliases if idiomatic for the platform, but arrow keys and WASD must work.

## State model

Implementations should model at least:

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
7. Console: selected cell has no color highlight — `X` only
8. Web: selected cell has no background or border color highlight — `X` only on the default cell background
9. `Q` or `q` on the grid screen quits the application
10. `L` or `l` on the grid screen returns to the login screen with the username field cleared and grid state reset

## Further reading

- [project.md](../project.md) — repository layout and conventions
- [README.md](README.md) — example overview and implementation index
