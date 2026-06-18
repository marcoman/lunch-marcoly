#!/usr/bin/env python3
"""Console grid navigator with LaunchDarkly flag variation evaluation."""

import curses
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flag_variations import evaluate_flags  # noqa: E402
from host_os import HOST_OS_ATTR, detect_host_os  # noqa: E402

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")

_ld_client: LDClient | None = None
_host_os = detect_host_os()


def init_launchdarkly() -> None:
    global _ld_client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        return
    ldclient.set_config(Config(sdk_key, private_attributes=[HOST_OS_ATTR]))
    _ld_client = ldclient.get()


def display_name(username: str, flags: dict) -> str:
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


def draw_cell(stdscr: curses.window, y: int, x: int, selected: bool) -> None:
    top = "┏━━━┓" if selected else "┌───┐"
    mid = "┃ X ┃" if selected else "│   │"
    bot = "┗━━━┛" if selected else "└───┘"
    stdscr.addstr(y, x, top)
    stdscr.addstr(y + 1, x, mid)
    stdscr.addstr(y + 2, x, bot)


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
    prev_text = format_pos(*previous) if previous else "—"
    line = 0
    stdscr.addstr(line, 0, f"Name: {display_name(username, flags)}")
    line += 1
    stdscr.addstr(line, 0, f"Current position: {format_pos(row, col)}")
    line += 1
    stdscr.addstr(line, 0, f"Previous position: {prev_text}")
    line += 1
    stdscr.addstr(line, 0, f"{flags['countLabel']}: {move_count}")
    line += 1
    stdscr.addstr(line, 0, f"Lucky Number is: {flags['luckyNumber']}")
    line += 2
    stdscr.addstr(line, 0, "Use arrow keys or WASD to move (L to logout, Q to quit).")

    base_y, base_x = line + 2, 2
    cell_w = 6
    for r in range(3):
        for c in range(3):
            draw_cell(
                stdscr,
                base_y + r * 4,
                base_x + c * cell_w,
                r == row and c == col,
            )
    stdscr.refresh()


def run_grid(stdscr: curses.window, username: str) -> str:
    row, col = 1, 1
    previous: tuple[int, int] | None = None
    move_count = 0
    stdscr.timeout(500)

    try:
        while True:
            flags = evaluate_flags(_ld_client, username, _host_os)
            max_moves = int(flags["maxMoves"])
            draw_screen(stdscr, username, row, col, previous, move_count, flags)
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

            if move_count >= max_moves:
                continue

            new_row, new_col, moved = try_move(row, col, dr, dc)
            if moved:
                previous = (row, col)
                row, col = new_row, new_col
                move_count += 1
    finally:
        stdscr.timeout(-1)


def main(stdscr: curses.window) -> None:
    curses.curs_set(0)
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
