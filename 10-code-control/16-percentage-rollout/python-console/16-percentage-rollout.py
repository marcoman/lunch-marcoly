#!/usr/bin/env python3
"""Console grid navigator for a static LaunchDarkly percentage rollout."""

from __future__ import annotations

import curses
import os
import sys
from pathlib import Path
from typing import Any

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rollout import evaluate_rollout  # noqa: E402

# LaunchDarkly: percentage rollout — sticky assignment by context key.
# https://launchdarkly.com/docs/home/flags/rollouts

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")
APP_BANNER = "16-percentage-rollout[python-console]"
CONFIGURED_GREEN_PCT = 30
HISTORY_LIMIT = 8
GREEN_PAIR = 5
INK_PAIR = 7

_ld_client: LDClient | None = None


def init_launchdarkly() -> None:
    """Initialize one process-wide SDK client for percentage evaluation."""
    global _ld_client
    sdk_key = (os.environ.get("LD_SDK_KEY") or "").strip()
    if not sdk_key:
        return
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()


def generated_username(base: str, index: int) -> str:
    """Map a sequence index onto a context key. 0 is the original login."""
    if index <= 0:
        return base
    return f"{base}{index}"


def format_pos(row: int, col: int) -> str:
    return f"{ROWS[row]}/{COLS[col]}"


def try_move(row: int, col: int, dr: int, dc: int) -> tuple[int, int, bool]:
    new_row = max(0, min(2, row + dr))
    new_col = max(0, min(2, col + dc))
    return new_row, new_col, (new_row, new_col) != (row, col)


def put(
    stdscr: curses.window, y: int, x: int, text: str, attr: int = curses.A_NORMAL
) -> None:
    try:
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass


def cell_attr(color: str) -> int:
    if color == "green":
        return curses.color_pair(GREEN_PAIR)
    return curses.A_NORMAL


def read_username(stdscr: curses.window) -> str:
    stdscr.timeout(-1)
    curses.echo()
    stdscr.clear()
    put(stdscr, 0, 0, APP_BANNER)
    put(stdscr, 2, 0, "Login")
    put(stdscr, 3, 0, "Username becomes the LaunchDarkly user context key.")
    put(stdscr, 5, 0, "Username: ")
    stdscr.refresh()
    while True:
        username = stdscr.getstr(5, 10, 40).decode("utf-8").strip()
        if username:
            curses.noecho()
            return username
        put(stdscr, 7, 0, "Username is required. Try again.")
        stdscr.clrtoeol()
        stdscr.refresh()


def draw_cell(
    stdscr: curses.window, y: int, x: int, selected: bool, color: str
) -> None:
    top = "┏━━━┓" if selected else "┌───┐"
    mid = "┃ X ┃" if selected else "│   │"
    bot = "┗━━━┛" if selected else "└───┘"
    attr = cell_attr(color) if selected else curses.A_NORMAL
    put(stdscr, y, x, top, attr)
    put(stdscr, y + 1, x, mid, attr)
    put(stdscr, y + 2, x, bot, attr)


def observed_line(seen: dict[str, str]) -> str:
    total = len(seen)
    if not total:
        return "Observed: no unique keys yet."
    green_count = sum(1 for value in seen.values() if value == "green")
    none_count = total - green_count
    pct = round((green_count / total) * 1000) / 10
    return (
        f"Observed: {green_count} green / {none_count} none of {total} unique "
        f"→ {pct}% (configured {CONFIGURED_GREEN_PCT}%)"
    )


def nav_hint(next_name: str, previous_name: str | None) -> str:
    prev = "—" if previous_name is None else previous_name
    return (
        f"Arrows/WASD move.  N next ({next_name})  P prev ({prev})  "
        "L logout  Q quit"
    )


def draw_screen(
    stdscr: curses.window,
    username: str,
    next_name: str,
    previous_name: str | None,
    row: int, col: int,
    previous: tuple[int, int] | None,
    flags: dict[str, Any],
    seen: dict[str, str],
    history: list[dict[str, str]],
) -> None:
    stdscr.clear()
    stdscr.bkgd(" ", curses.color_pair(INK_PAIR))
    color = str(flags.get("highlightColor") or "none")
    reason = flags.get("reason") or {}
    reason_kind = str(reason.get("kind") or "UNKNOWN")
    variation = flags.get("variationIndex")
    variation_text = "default" if variation is None else str(variation)

    put(stdscr, 0, 0, APP_BANNER)
    put(stdscr, 1, 0, "Name: ")
    put(stdscr, 1, 6, username, cell_attr(color))
    prev_text = format_pos(*previous) if previous else "—"
    put(
        stdscr,
        2,
        0,
        f"Current: {format_pos(row, col)}   Previous: {prev_text}",
    )
    put(
        stdscr,
        3,
        0,
        f"Flag value: {flags.get('flagValue')}   reason: {reason_kind}   "
        f"idx: {variation_text}",
    )
    put(stdscr, 4, 0, observed_line(seen))
    put(stdscr, 5, 0, nav_hint(next_name, previous_name))

    base_y, base_x = 7, 2
    for r in range(3):
        for c in range(3):
            selected = r == row and c == col
            draw_cell(
                stdscr,
                base_y + r * 4,
                base_x + c * 6,
                selected,
                color if selected else "none",
            )

    hist_x = 24
    put(stdscr, base_y, hist_x, "Recent evaluations")
    if not history:
        put(stdscr, base_y + 1, hist_x, "(none yet)", curses.A_DIM)
    for index, item in enumerate(history):
        label = f"{item['username']}  {item['value']}  {item['reason']}"
        attr = cell_attr(item["value"])
        put(stdscr, base_y + 1 + index, hist_x, label, attr)
    stdscr.refresh()


def remember(
    username: str,
    flags: dict[str, Any],
    seen: dict[str, str],
    history: list[dict[str, str]],
) -> None:
    value = str(flags.get("flagValue") or "none")
    reason = str((flags.get("reason") or {}).get("kind") or "UNKNOWN")
    seen[username] = value
    history[:] = [item for item in history if item["username"] != username]
    history.insert(0, {"username": username, "value": value, "reason": reason})
    del history[HISTORY_LIMIT:]


def run_grid(stdscr: curses.window, base_username: str) -> str:
    """Navigate the grid and walk generated usernames with N / P.

    Index 0 is the original login. N steps forward (marco → marco1 → marco2);
    P steps back and stops at the login name. LaunchDarkly still owns
    assignment; this loop only changes the context key and re-evaluates.
    """
    index = 0
    username = generated_username(base_username, index)
    row, col = 1, 1
    previous: tuple[int, int] | None = None
    seen: dict[str, str] = {}
    history: list[dict[str, str]] = []
    stdscr.timeout(500)
    try:
        while True:
            flags = evaluate_rollout(_ld_client, username)
            remember(username, flags, seen, history)
            draw_screen(
                stdscr,
                username,
                generated_username(base_username, index + 1),
                None if index == 0 else generated_username(base_username, index - 1),
                row,
                col,
                previous,
                flags,
                seen,
                history,
            )
            key = stdscr.getch()
            if key == -1:
                continue
            if key in (ord("q"), ord("Q")):
                return "quit"
            if key in (ord("l"), ord("L")):
                return "logout"
            if key in (ord("n"), ord("N")):
                index += 1
                username = generated_username(base_username, index)
                row, col = 1, 1
                previous = None
                continue
            if key in (ord("p"), ord("P")):
                if index == 0:
                    continue
                index -= 1
                username = generated_username(base_username, index)
                row, col = 1, 1
                previous = None
                continue

            dr = dc = 0
            if key in (curses.KEY_UP, ord("w"), ord("W")):
                dr = -1
            elif key in (curses.KEY_DOWN, ord("s"), ord("S")):
                dr = 1
            elif key in (curses.KEY_LEFT, ord("a"), ord("A")):
                dc = -1
            elif key in (curses.KEY_RIGHT, ord("d"), ord("D")):
                dc = 1
            else:
                continue

            new_row, new_col, moved = try_move(row, col, dr, dc)
            if moved:
                previous = (row, col)
                row, col = new_row, new_col
    finally:
        stdscr.timeout(-1)


def init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(GREEN_PAIR, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(INK_PAIR, curses.COLOR_WHITE, curses.COLOR_BLACK)


def main(stdscr: curses.window) -> None:
    curses.curs_set(0)
    init_colors()
    stdscr.keypad(True)
    init_launchdarkly()
    try:
        while True:
            username = read_username(stdscr)
            if run_grid(stdscr, username) == "quit":
                break
    finally:
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    curses.wrapper(main)
