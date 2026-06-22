#!/usr/bin/env python3
"""Console grid navigator with ABCD navigation count label (LaunchDarkly string flag)."""

import curses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from abcd_eval import close_client, evaluate_count_label, init_client

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")


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
    count_label: str,
) -> None:
    stdscr.clear()
    prev_text = format_pos(*previous) if previous else "—"
    stdscr.addstr(0, 0, f"Name: {username}")
    stdscr.addstr(1, 0, f"Current position: {format_pos(row, col)}")
    stdscr.addstr(2, 0, f"Previous position: {prev_text}")
    stdscr.addstr(3, 0, f"{count_label}: {move_count}")
    stdscr.addstr(5, 0, "Use arrow keys or WASD to move (L to logout, Q to quit).")

    base_y, base_x = 7, 2
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
    count_label = evaluate_count_label(username)

    while True:
        draw_screen(stdscr, username, row, col, previous, move_count, count_label)
        key = stdscr.getch()

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


def main(stdscr: curses.window) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    init_client()

    try:
        while True:
            username = read_username(stdscr)
            if run_grid(stdscr, username) == "quit":
                break
    finally:
        close_client()


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--evaluate-once":
        init_client()
        try:
            print(evaluate_count_label(sys.argv[2]))
        finally:
            close_client()
        sys.exit(0)

    curses.wrapper(main)
