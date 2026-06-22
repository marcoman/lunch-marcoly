#!/usr/bin/env python3
"""Console grid navigator with LaunchDarkly segment-by-name context targeting."""

import curses
import json
import os
import sys
import time
from pathlib import Path

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from segment_context import build_segment_context, FLAG_HIGHLIGHT  # noqa: E402
from segment_style import evaluate_highlight  # noqa: E402

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")

COLOR_PAIRS = {
    "yellow": 1,
    "red": 2,
    "blue": 3,
    "green": 4,
    "purple": 5,
}

_ld_client: LDClient | None = None


def wait_for_ld(client: LDClient, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.is_initialized():
            return True
        time.sleep(0.05)
    return client.is_initialized()


def init_launchdarkly() -> bool:
    global _ld_client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        print("Warning: LD_SDK_KEY not set — highlight defaults to off.", flush=True)
        return False
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()
    if not wait_for_ld(_ld_client):
        print("Warning: LaunchDarkly SDK did not initialize — highlight defaults to off.", flush=True)
        return False
    return True


def format_pos(row: int, col: int) -> str:
    return f"{ROWS[row]}/{COLS[col]}"


def try_move(row: int, col: int, dr: int, dc: int) -> tuple[int, int, bool]:
    new_row = max(0, min(2, row + dr))
    new_col = max(0, min(2, col + dc))
    if new_row == row and new_col == col:
        return row, col, False
    return new_row, new_col, True


def read_username(stdscr: curses.window) -> str:
    stdscr.timeout(-1)
    curses.echo()
    stdscr.clear()
    stdscr.addstr(0, 0, "Login")
    stdscr.addstr(2, 0, "Username: ")
    stdscr.refresh()
    while True:
        username = stdscr.getstr(2, 10, 40).decode("utf-8").strip()
        if username:
            curses.noecho()
            return username
        stdscr.addstr(4, 0, "Username is required. Try again.")
        stdscr.clrtoeol()
        stdscr.refresh()


def cell_attr(color: str) -> int:
    if color == "none":
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


def draw_name_line(stdscr: curses.window, y: int, username: str, flags: dict) -> None:
    stdscr.addstr(y, 0, "Name: ")
    color = str(flags["highlightColor"])
    label = str(flags["segmentLabel"])
    attr = cell_attr(color) if color != "none" else curses.A_NORMAL
    stdscr.addstr(y, 6, username, attr)
    stdscr.addstr(f" {label}", attr)


def draw_screen(
    stdscr: curses.window,
    username: str,
    row: int,
    col: int,
    previous: tuple[int, int] | None,
    flags: dict[str, object],
) -> None:
    stdscr.clear()
    stdscr.bkgd(" ", curses.color_pair(6))
    prev_text = format_pos(*previous) if previous else "—"
    line = 0
    draw_name_line(stdscr, line, username, flags)
    line += 1
    stdscr.addstr(line, 0, f"Current position: {format_pos(row, col)}")
    line += 1
    stdscr.addstr(line, 0, f"Previous position: {prev_text}")
    line += 2
    stdscr.addstr(line, 0, "Use arrow keys or WASD to move (L to logout, Q to quit).")

    highlight_color = str(flags["highlightColor"])
    cell_color = highlight_color if highlight_color != "none" else "none"

    base_y, base_x = line + 2, 2
    cell_w = 6
    for r in range(3):
        for c in range(3):
            draw_cell(
                stdscr,
                base_y + r * 4,
                base_x + c * cell_w,
                r == row and c == col,
                cell_color if r == row and c == col else "none",
            )
    stdscr.refresh()


def run_grid(stdscr: curses.window, username: str) -> str:
    row, col = 1, 1
    previous: tuple[int, int] | None = None
    stdscr.timeout(500)

    try:
        while True:
            flags = evaluate_highlight(_ld_client, username)
            draw_screen(stdscr, username, row, col, previous, flags)
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
    finally:
        stdscr.timeout(-1)


def init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(COLOR_PAIRS["yellow"], curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(COLOR_PAIRS["red"], curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(COLOR_PAIRS["blue"], curses.COLOR_BLUE, curses.COLOR_BLACK)
    curses.init_pair(COLOR_PAIRS["green"], curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(COLOR_PAIRS["purple"], curses.COLOR_MAGENTA, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLACK)


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


def evaluate_once(username: str, *, verbose: bool = False) -> None:
    init_launchdarkly()
    try:
        if verbose:
            context, info = build_segment_context(username)
            diag: dict[str, object] = {
                "username": username,
                "sdkInitialized": _ld_client is not None and _ld_client.is_initialized(),
                "segmentInfo": {
                    "segmentType": info.segment_type,
                    "namedColor": info.named_color,
                },
                "context": json.loads(context.to_json_string()),
            }
            if _ld_client is not None and _ld_client.is_initialized():
                detail = _ld_client.variation_detail(FLAG_HIGHLIGHT, context, "none")
                diag["rawVariation"] = detail.value
                diag["variationIndex"] = detail.variation_index
                diag["reason"] = detail.reason
            result = evaluate_highlight(_ld_client, username)
            diag["result"] = result
            print(json.dumps(diag, indent=2))
        else:
            print(json.dumps(evaluate_highlight(_ld_client, username)))
    finally:
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--evaluate-once":
        username = sys.argv[2]
        verbose = "--verbose" in sys.argv[3:]
        evaluate_once(username, verbose=verbose)
        sys.exit(0)

    curses.wrapper(main)
