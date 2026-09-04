# Mobile reference application specification

This document defines the behavior of **51-reference** — a phone-sized grid
navigator for the [50-mobile](../README.md) series.

It is **not** a port of [00-reference-code](../../00-reference-code/application.md)
or [02-reference-client-code](../../02-reference-client-code/application.md).
Those apps are a 3×3 keyboard navigator. This app is a **2×2 tap** navigator
with a **lab drawer**. There is no WASD, no quit, and no AgentControl.

Repository layout is in [project.md](../../project.md). LaunchDarkly arrives in
a later **52** example. **51 has no LaunchDarkly.**

## Overview

A two-screen application implemented natively on **Android** and **iOS**:

1. **Login** — collect a username (no password), with a short explanation
2. **Grid** — 2×2 cells; move by tapping an orthogonally adjacent square

Selection is indicated by **`X` only** — no highlight colors.

Implementations must produce equivalent behavior. Differences are limited to
platform chrome (Material vs SwiftUI).

## Login screen

| Rule | Detail |
|------|--------|
| Fields | Username only — no password field |
| Validation | Username must be non-empty (after trim) before continuing |
| Explanation | Brief copy that this is a 2×2 tap lab (not the web WASD grid) |
| On submit | Proceed to the grid screen; display the username in the grid header |

The username persists for the session until logout. Killing and relaunching the
app returns to the login screen.

When LaunchDarkly is added in 52, this username becomes the context `key`.
51 does not initialize an SDK.

## Grid screen

### Grid layout

The main section is a **2×2 grid**:

| | Left (`l`) | Right (`r`) |
|---|------------|-------------|
| **Top (`t`)** | `t/l` | `t/r` |
| **Bottom (`b`)** | `b/l` | `b/r` |

Internally, positions use **row/column** abbreviations:

- Rows: `t` (top), `b` (bottom) — **no** `m`
- Columns: `l` (left), `r` (right) — **no** `m`
- Position notation: `{row}/{col}` — for example `t/l`, `b/r`

### Starting position

The cursor starts at **`t/l`** when the grid screen first loads. There is no
center cell.

### Navigation

The user moves by **tapping a cell**.

| Tap | Action |
|-----|--------|
| Current cell | No-op (position unchanged) |
| Orthogonally adjacent cell | Move there (one row **or** one column, not both) |
| Diagonal / opposite corner | Rejected — two taps away (same “no jump” idea as 00) |

**Orthogonal** means sharing a side: from `t/l` the legal taps are `t/r` and
`b/l`. `b/r` is illegal in one tap.

**Edge / illegal tap:** position unchanged. **Wrap-around is not permitted.**

| Current | Tap | Result |
|---------|-----|--------|
| `t/l` | `t/l` | `t/l` (unchanged) |
| `t/l` | `t/r` | `t/r` |
| `t/l` | `b/l` | `b/l` |
| `t/l` | `b/r` | `t/l` (unchanged) |
| `t/r` | `b/l` | `t/r` (unchanged — diagonal) |

There are no arrow keys, WASD, or swipe-to-move. (Swipe **opens the drawer**;
it must not move the `X`.)

### Session control

| Control | Action |
|---------|--------|
| **Logout** | Return to the login screen |
| Quit | **None** — use the OS back/home gesture |

**Logout:**

- Return to the login screen without exiting the process
- Clear the username field
- Reset grid state: current position `t/l`, previous position `—`
- Close the drawer if it was open
- The user may log in again with the same or a different username

Place **Logout** in the grid header (always visible). Do not require the drawer
to log out.

### Screen layout

#### Header

Always visible on the grid screen:

| Field | Content |
|-------|---------|
| Name | Username from login |
| Current position | Selected cell in `{row}/{col}` notation (e.g. `t/l`) |
| Previous position | Position before the last **successful** move |
| Logout | Button |

On the first render after login, **Previous position** is `—` (em dash).

After each successful move, **Previous position** updates to the cell held
before that move. Rejected taps (current cell, diagonal, or any no-op) do
**not** update **Previous position**.

#### Main section

Renders the 2×2 grid. The selected cell is marked with an **`X`**.

Unselected cells are empty (no marker).

Example at `t/l`:

```
┌───┬───┐
│ X │   │
├───┼───┤
│   │   │
└───┴───┘
```

(Exact borders and spacing may vary; cell contents and selection must not.)

#### Lab drawer

Extra information that would be a side rail on the web lives in a **drawer**:

- Open: swipe from the **leading** (left) screen edge, or tap a thin handle
  on that edge
- Close: swipe the drawer away, tap the scrim, or log out
- Must not cover the whole grid while closed; the 2×2 remains the hero

Drawer contents for 51:

| Field | Content |
|-------|---------|
| Current position | Same as header |
| Previous position | Same as header |
| Legal moves | The two (or fewer) orthogonal neighbors of the current cell |
| Hint | Tap an adjacent square. Opposite corner takes two taps. |

Later examples may add flag values and SDK logs here. 51 has no SDK lines.

## Presentation

- Default color scheme: **light mode**
- **No selection colors** — the selected cell is not highlighted with a
  background or border color distinct from unselected cells
- **Selected cell:** `X` centered on the same background as unselected cells
- Header and drawer: readable contrast; they are chrome, not the selection

## State model

| State | Type | Notes |
|-------|------|-------|
| `username` | string | Set at login |
| `current` | position | `{row}/{col}` |
| `previous` | position \| null | `null` until first successful move |
| `drawerOpen` | boolean | UI only; not part of navigator identity |

```text
position = { row: "t" | "b", col: "l" | "r" }
```

Display `previous` as `—` when null.

## Acceptance criteria

An implementation is correct when:

1. Login accepts a non-empty username and rejects an empty one
2. Grid starts at `t/l` with Previous position `—`
3. Tapping an orthogonal neighbor moves one step; the selected cell shows **X**
4. Tapping the current cell, or the diagonal opposite, leaves position and
   Previous unchanged
5. Header shows Name, Current, and Previous accurately after every change
6. Unselected cells have no `X`
7. Selected cell has no color highlight — `X` only
8. Logout returns to login with the username field cleared and grid reset to
   `t/l` / `—`
9. There is no quit control
10. Drawer opens from the leading edge and shows current, previous, and legal
    moves without being required for logout

## Further reading

- [project.md](../../project.md) — repository layout and conventions
- [README.md](README.md) — example overview
- [50-mobile/README.md](../README.md) — series credentials and platforms
