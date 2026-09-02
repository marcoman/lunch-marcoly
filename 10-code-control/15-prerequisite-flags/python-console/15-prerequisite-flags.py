#!/usr/bin/env python3
"""Console grid navigator demonstrating LaunchDarkly flag prerequisites."""

import curses
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from prerequisite import evaluate_prerequisite_flags  # noqa: E402

# LaunchDarkly: evaluate the dependent flag even when its prerequisite fails.
# https://launchdarkly.com/docs/home/flags/prereqs

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")
APP_BANNER = "15-prerequisite-flags[python-console]"
COLOR_PAIRS = {
    "pink": 1,
    "yellow": 2,
    "red": 3,
    "blue": 4,
    "green": 5,
    "purple": 6,
}

_ld_client: LDClient | None = None


def init_launchdarkly() -> None:
    """Initialize the server SDK used for both detailed evaluations."""
    global _ld_client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        return
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()


def format_reason(detail: dict) -> str:
    reason = detail.get("reason") or {}
    kind = str(reason.get("kind") or "UNKNOWN")
    key = reason.get("prerequisiteKey")
    return f"{kind} ({key})" if key else kind


def format_pos(row: int, col: int) -> str:
    return f"{ROWS[row]}/{COLS[col]}"


def try_move(row: int, col: int, dr: int, dc: int) -> tuple[int, int, bool]:
    new_row = max(0, min(2, row + dr))
    new_col = max(0, min(2, col + dc))
    return new_row, new_col, (new_row, new_col) != (row, col)


def read_username(stdscr: curses.window) -> str:
    stdscr.timeout(-1)
    curses.echo()
    stdscr.clear()
    stdscr.addstr(0, 0, APP_BANNER)
    stdscr.addstr(2, 0, "Login")
    stdscr.addstr(4, 0, "Username: ")
    stdscr.refresh()
    while True:
        username = stdscr.getstr(4, 10, 40).decode("utf-8").strip()
        if username:
            curses.noecho()
            return username
        stdscr.addstr(6, 0, "Username is required. Try again.")
        stdscr.clrtoeol()
        stdscr.refresh()


def cell_attr(color: str) -> int:
    if color == "none" or color not in COLOR_PAIRS:
        return curses.A_NORMAL
    return curses.color_pair(COLOR_PAIRS[color])


def draw_cell(
    stdscr: curses.window, y: int, x: int, selected: bool, color: str
) -> None:
    top = "┏━━━┓" if selected else "┌───┐"
    mid = "┃ X ┃" if selected else "│   │"
    bot = "┗━━━┛" if selected else "└───┘"
    attr = cell_attr(color) if selected else curses.A_NORMAL
    stdscr.addstr(y, x, top, attr)
    stdscr.addstr(y + 1, x, mid, attr)
    stdscr.addstr(y + 2, x, bot, attr)


def draw_screen(
    stdscr: curses.window,
    username: str,
    row: int,
    col: int,
    previous: tuple[int, int] | None,
    move_count: int,
    flags: dict,
) -> None:
    stdscr.clear()
    stdscr.bkgd(" ", curses.color_pair(7))
    prev_text = format_pos(*previous) if previous else "—"
    color = str(flags["highlightColor"])
    line = 0
    stdscr.addstr(line, 0, APP_BANNER)
    line += 1
    stdscr.addstr(line, 0, "Name: ")
    stdscr.addstr(username, cell_attr(color) if color != "none" else curses.A_NORMAL)
    line += 1
    stdscr.addstr(line, 0, f"Current position: {format_pos(row, col)}")
    line += 1
    stdscr.addstr(line, 0, f"Previous position: {prev_text}")
    if flags["showMoveCount"]:
        line += 1
        stdscr.addstr(line, 0, f"Count: {move_count}")
    line += 2
    parent = flags["parent"]
    child = flags["child"]
    stdscr.addstr(line, 0, f"Parent: {parent['value']}  {format_reason(parent)}")
    line += 1
    stdscr.addstr(line, 0, f"Child:  {child['value']}  {format_reason(child)}")
    line += 2
    stdscr.addstr(line, 0, "Use arrow keys or WASD to move (L to logout, Q to quit).")

    base_y, base_x = line + 2, 2
    for r in range(3):
        for c in range(3):
            draw_cell(
                stdscr,
                base_y + r * 4,
                base_x + c * 6,
                r == row and c == col,
                color if r == row and c == col else "none",
            )
    stdscr.refresh()


def run_grid(stdscr: curses.window, username: str) -> str:
    """Re-evaluate parent and child every 500 ms; LaunchDarkly enforces the prerequisite."""
    row, col = 1, 1
    previous: tuple[int, int] | None = None
    move_count = 0
    stdscr.timeout(500)
    try:
        while True:
            flags = evaluate_prerequisite_flags(_ld_client, username)
            draw_screen(stdscr, flags["username"], row, col, previous, move_count, flags)
            key = stdscr.getch()
            if key == -1:
                continue
            if key in (ord("q"), ord("Q")):
                return "quit"
            if key in (ord("l"), ord("L")):
                return "logout"

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
                move_count += 1
    finally:
        stdscr.timeout(-1)


def init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_PAIRS["pink"], curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(COLOR_PAIRS["yellow"], curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(COLOR_PAIRS["red"], curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(COLOR_PAIRS["blue"], curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(COLOR_PAIRS["green"], curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(COLOR_PAIRS["purple"], curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)


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
