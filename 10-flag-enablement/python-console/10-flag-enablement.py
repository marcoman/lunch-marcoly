#!/usr/bin/env python3
"""Console grid navigator with LaunchDarkly flag evaluation."""

import curses
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from highlight_style import (  # noqa: E402
    FLAG_CONTEXT,
    FLAG_COUNT,
    FLAG_HIGHLIGHT,
    build_flag_response,
)
from host_os import (  # noqa: E402
    FLAG_OS_EMOJI,
    HOST_OS_ATTR,
    build_evaluation_context,
    detect_host_os,
)

# LaunchDarkly capability: Boolean flag evaluation (server-side SDK)
# Private attribute hostOs is set on the evaluation context for targeting.
# See: https://launchdarkly.com/docs/sdk/features/private-attributes

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")

COLOR_PAIRS = {
    "pink": 1,
    "yellow": 2,
    "red": 3,
    "blue": 4,
    "green": 5,
    "purple": 6,
}

_ld_client: LDClient | None = None
_host_os = detect_host_os()


def init_launchdarkly() -> None:
    global _ld_client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        return
    ldclient.set_config(Config(sdk_key, private_attributes=[HOST_OS_ATTR]))
    _ld_client = ldclient.get()


def evaluate_flags(username: str) -> dict[str, object]:
    if _ld_client is None or not _ld_client.is_initialized():
        return build_flag_response(username, False, False, False, False, _host_os)
    context, host_os = build_evaluation_context(username)
    highlight = bool(_ld_client.variation(FLAG_HIGHLIGHT, context, False))
    context_highlight = bool(_ld_client.variation(FLAG_CONTEXT, context, False))
    show_count = bool(_ld_client.variation(FLAG_COUNT, context, False))
    show_os_emoji = bool(_ld_client.variation(FLAG_OS_EMOJI, context, False))
    return build_flag_response(
        username, highlight, context_highlight, show_count, show_os_emoji, host_os
    )


def display_name(username: str, flags: dict[str, object]) -> str:
    emoji = str(flags.get("osEmoji", ""))
    if emoji:
        return f"{emoji} {username}"
    return username


def format_pos(row: int, col: int) -> str:
    return f"{ROWS[row]}/{COLS[col]}"


def try_move(row: int, col: int, dr: int, dc: int) -> tuple[int, int, bool]:
    new_row = max(0, min(2, row + dr))
    new_col = max(0, min(2, col + dc))
    if new_row == row and new_col == col:
        return row, col, False
    return new_row, new_col, True


def read_username(stdscr: curses.window) -> str:
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
    label = str(flags["cohortLabel"])
    name = display_name(username, flags)
    attr = cell_attr(color) if color != "none" else curses.A_NORMAL
    stdscr.addstr(y, 6, name, attr)
    stdscr.addstr(f" {label}", attr)


def draw_screen(
    stdscr: curses.window,
    username: str,
    row: int,
    col: int,
    previous: tuple[int, int] | None,
    move_count: int,
    flags: dict[str, object],
) -> None:
    stdscr.clear()
    stdscr.bkgd(" ", curses.color_pair(7))
    prev_text = format_pos(*previous) if previous else "—"
    line = 0
    draw_name_line(stdscr, line, username, flags)
    line += 1
    stdscr.addstr(line, 0, f"Current position: {format_pos(row, col)}")
    line += 1
    stdscr.addstr(line, 0, f"Previous position: {prev_text}")
    if flags["showMoveCount"]:
        line += 1
        stdscr.addstr(line, 0, f"Count: {move_count}")
    line += 2
    stdscr.addstr(line, 0, "Use arrow keys or WASD to move (q to quit).")

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


def run_grid(stdscr: curses.window, username: str) -> None:
    row, col = 1, 1
    previous: tuple[int, int] | None = None
    move_count = 0
    stdscr.timeout(500)

    while True:
        flags = evaluate_flags(username)
        draw_screen(stdscr, username, row, col, previous, move_count, flags)
        key = stdscr.getch()
        if key == -1:
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
        elif key in (ord("q"), ord("Q")):
            break
        else:
            continue

        new_row, new_col, moved = try_move(row, col, dr, dc)
        if moved:
            previous = (row, col)
            row, col = new_row, new_col
            move_count += 1


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
    username = read_username(stdscr)
    try:
        run_grid(stdscr, username)
    finally:
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    curses.wrapper(main)
