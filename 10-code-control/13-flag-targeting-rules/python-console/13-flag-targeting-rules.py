#!/usr/bin/env python3
"""Console grid navigator demonstrating LaunchDarkly targeting rules."""

import curses
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from team_style import evaluate_team_style  # noqa: E402

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")
TEAMS = {"1": "", "2": "red", "3": "blue", "4": "yellow"}
APP_BANNER = "13-flag-targeting-rules[python-console]"

_ld_client: LDClient | None = None


def init_launchdarkly() -> None:
    """Initialize the server SDK without private context attributes."""
    global _ld_client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        return
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()


def init_colors() -> dict[str, int]:
    """Create curses pairs for the three colored flag variations."""
    if not curses.has_colors():
        return {}
    curses.start_color()
    curses.use_default_colors()
    pairs = {
        "colored-red": (1, curses.COLOR_RED),
        "colored-blue": (2, curses.COLOR_BLUE),
        "colored-yellow": (3, curses.COLOR_YELLOW),
    }
    for _, (pair, color) in pairs.items():
        curses.init_pair(pair, color, -1)
    return {style: curses.color_pair(pair) for style, (pair, _) in pairs.items()}


def format_pos(row: int, col: int) -> str:
    return f"{ROWS[row]}/{COLS[col]}"


def try_move(row: int, col: int, dr: int, dc: int) -> tuple[int, int, bool]:
    new_row = max(0, min(2, row + dr))
    new_col = max(0, min(2, col + dc))
    return new_row, new_col, (new_row, new_col) != (row, col)


def read_login(stdscr: curses.window) -> tuple[str, str]:
    """Prompt for a user key and the public team attribute used by rules."""
    stdscr.timeout(-1)
    curses.echo()
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, APP_BANNER)
        stdscr.addstr(2, 0, "Login")
        stdscr.addstr(4, 0, "Username: ")
        stdscr.refresh()
        username = stdscr.getstr(4, 10, 40).decode("utf-8").strip()
        if not username:
            stdscr.addstr(6, 0, "Username is required. Try again.")
            stdscr.refresh()
            stdscr.getch()
            continue

        while True:
            stdscr.addstr(6, 0, "Team [1=None 2=Red 3=Blue 4=Yellow]: ")
            stdscr.clrtoeol()
            stdscr.refresh()
            choice = stdscr.getstr(6, 40, 1).decode("utf-8").strip()
            if choice in TEAMS:
                curses.noecho()
                return username, TEAMS[choice]
            stdscr.addstr(8, 0, "Choose 1, 2, 3, or 4.")
            stdscr.clrtoeol()
            stdscr.refresh()


def draw_cell(stdscr: curses.window, y: int, x: int, selected: bool) -> None:
    lines = ("┏━━━┓", "┃ X ┃", "┗━━━┛") if selected else ("┌───┐", "│   │", "└───┘")
    for offset, text in enumerate(lines):
        stdscr.addstr(y + offset, x, text)


def draw_screen(
    stdscr: curses.window,
    username: str,
    row: int,
    col: int,
    previous: tuple[int, int] | None,
    style: dict,
    color_pairs: dict[str, int],
) -> None:
    stdscr.clear()
    stdscr.addstr(0, 0, APP_BANNER)
    stdscr.addstr(1, 0, f"Name: {username}")
    stdscr.addstr(2, 0, "Team: ")
    stdscr.addstr(style["teamLabel"], color_pairs.get(style["style"], curses.A_NORMAL))
    stdscr.addstr(3, 0, f"Current position: {format_pos(row, col)}")
    prev_text = format_pos(*previous) if previous else "—"
    stdscr.addstr(4, 0, f"Previous position: {prev_text}")
    stdscr.addstr(6, 0, "Use arrow keys or WASD to move (L to logout, Q to quit).")

    for r in range(3):
        for c in range(3):
            draw_cell(stdscr, 8 + r * 4, 2 + c * 6, r == row and c == col)
    stdscr.refresh()


def run_grid(
    stdscr: curses.window,
    username: str,
    team: str,
    color_pairs: dict[str, int],
) -> str:
    """Re-evaluate the team style every 500 ms while navigating."""
    row, col = 1, 1
    previous: tuple[int, int] | None = None
    stdscr.timeout(500)
    try:
        while True:
            style = evaluate_team_style(_ld_client, username, team)
            draw_screen(stdscr, username, row, col, previous, style, color_pairs)
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


def main(stdscr: curses.window) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    color_pairs = init_colors()
    init_launchdarkly()
    try:
        while True:
            username, team = read_login(stdscr)
            if run_grid(stdscr, username, team, color_pairs) == "quit":
                break
    finally:
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    curses.wrapper(main)
