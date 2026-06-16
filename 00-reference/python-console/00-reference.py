#!/usr/bin/env python3
"""Console grid navigator: username login and 3×3 keyboard navigation."""

import curses

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")


def format_pos(row: int, col: int) -> str:
    return f"{ROWS[row]}/{COLS[col]}"


def try_move(row: int, col: int, dr: int, dc: int) -> tuple[int, int, bool]:
    """Return new (row, col) and whether the position changed."""
    new_row = max(0, min(2, row + dr))
    new_col = max(0, min(2, col + dc))
    if new_row == row and new_col == col:
        return row, col, False
    return new_row, new_col, True


def read_username(stdscr: curses.window) -> str:
    """Prompt for a non-empty username (no password)."""
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
    """Draw one grid cell; selected cells show X with no color highlight."""
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
) -> None:
    stdscr.clear()
    prev_text = format_pos(*previous) if previous else "—"
    stdscr.addstr(0, 0, f"Name: {username}")
    stdscr.addstr(1, 0, f"Current position: {format_pos(row, col)}")
    stdscr.addstr(2, 0, f"Previous position: {prev_text}")
    stdscr.addstr(4, 0, "Use arrow keys or WASD to move (L to logout, Q to quit).")

    base_y, base_x = 6, 2
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

    while True:
        draw_screen(stdscr, username, row, col, previous)
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


def main(stdscr: curses.window) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)

    while True:
        username = read_username(stdscr)
        if run_grid(stdscr, username) == "quit":
            break


if __name__ == "__main__":
    curses.wrapper(main)
