#!/usr/bin/env python3
"""Console grid navigator demonstrating LaunchDarkly multi-context targeting."""

import curses
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from partner import evaluate_partner  # noqa: E402

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")
USERS = {"1": "alice", "2": "bob"}
ORGS = {"1": "acme", "2": "globex"}
APP_BANNER = "14-multi-context-targeting[python-console]"

_ld_client: LDClient | None = None


def init_launchdarkly() -> None:
    """Initialize the server SDK for user + organization multi-context evaluation."""
    global _ld_client
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        return
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()


def init_colors() -> int:
    """Green pair for the partner badge when the flag is true."""
    if not curses.has_colors():
        return curses.A_BOLD
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    return curses.color_pair(1) | curses.A_BOLD


def format_pos(row: int, col: int) -> str:
    return f"{ROWS[row]}/{COLS[col]}"


def try_move(row: int, col: int, dr: int, dc: int) -> tuple[int, int, bool]:
    new_row = max(0, min(2, row + dr))
    new_col = max(0, min(2, col + dc))
    return new_row, new_col, (new_row, new_col) != (row, col)


def read_login(stdscr: curses.window) -> tuple[str, str]:
    """Prompt for Alice/Bob and Acme/Globex — the two multi-context keys."""
    stdscr.timeout(-1)
    curses.echo()
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, APP_BANNER)
        stdscr.addstr(2, 0, "Login")
        stdscr.addstr(4, 0, "User [1=Alice 2=Bob]: ")
        stdscr.refresh()
        user_choice = stdscr.getstr(4, 24, 1).decode("utf-8").strip()
        if user_choice not in USERS:
            stdscr.addstr(6, 0, "Choose 1 or 2.")
            stdscr.refresh()
            stdscr.getch()
            continue
        while True:
            stdscr.addstr(6, 0, "Org  [1=Acme 2=Globex]: ")
            stdscr.clrtoeol()
            stdscr.refresh()
            org_choice = stdscr.getstr(6, 25, 1).decode("utf-8").strip()
            if org_choice in ORGS:
                curses.noecho()
                return USERS[user_choice], ORGS[org_choice]
            stdscr.addstr(8, 0, "Choose 1 or 2.")
            stdscr.clrtoeol()
            stdscr.refresh()


def draw_cell(stdscr: curses.window, y: int, x: int, selected: bool) -> None:
    lines = ("┏━━━┓", "┃ X ┃", "┗━━━┛") if selected else ("┌───┐", "│   │", "└───┘")
    for offset, text in enumerate(lines):
        stdscr.addstr(y + offset, x, text)


def draw_screen(
    stdscr: curses.window,
    username: str,
    org: str,
    row: int,
    col: int,
    previous: tuple[int, int] | None,
    flags: dict,
    badge_attr: int,
) -> None:
    stdscr.clear()
    stdscr.addstr(0, 0, APP_BANNER)
    stdscr.addstr(1, 0, f"Name: {username}")
    if flags.get("partner"):
        stdscr.addstr("  ")
        stdscr.addstr("partner", badge_attr)
    stdscr.addstr(2, 0, f"Org: {flags.get('orgLabel') or org}")
    stdscr.addstr(3, 0, f"Current position: {format_pos(row, col)}")
    prev_text = format_pos(*previous) if previous else "—"
    stdscr.addstr(4, 0, f"Previous position: {prev_text}")
    stdscr.addstr(
        6,
        0,
        "1/2 user Alice/Bob, 3/4 org Acme/Globex. Arrows or WASD. L logout, Q quit.",
    )

    for r in range(3):
        for c in range(3):
            draw_cell(stdscr, 8 + r * 4, 2 + c * 6, r == row and c == col)
    stdscr.refresh()


def run_grid(
    stdscr: curses.window,
    username: str,
    org: str,
    badge_attr: int,
) -> str:
    """Re-evaluate the partner badge every 500 ms; 1–4 walk the 2×2 without logout."""
    row, col = 1, 1
    previous: tuple[int, int] | None = None
    stdscr.timeout(500)
    try:
        while True:
            flags = evaluate_partner(_ld_client, username, org)
            draw_screen(stdscr, username, org, row, col, previous, flags, badge_attr)
            key = stdscr.getch()
            if key == -1:
                continue
            if key in (ord("q"), ord("Q")):
                return "quit"
            if key in (ord("l"), ord("L")):
                return "logout"
            if key == ord("1"):
                username = "alice"
                continue
            if key == ord("2"):
                username = "bob"
                continue
            if key == ord("3"):
                org = "acme"
                continue
            if key == ord("4"):
                org = "globex"
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


def main(stdscr: curses.window) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    badge_attr = init_colors()
    init_launchdarkly()
    try:
        while True:
            username, org = read_login(stdscr)
            if run_grid(stdscr, username, org, badge_attr) == "quit":
                break
    finally:
        if _ld_client is not None:
            _ld_client.close()


if __name__ == "__main__":
    curses.wrapper(main)
