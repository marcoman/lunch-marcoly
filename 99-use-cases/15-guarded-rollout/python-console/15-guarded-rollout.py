#!/usr/bin/env python3
"""Console grid navigator — guarded rollout of a single LaunchDarkly highlight flag.

In this example, we have a guarded rollout over 12 minutes in four equal stages:
10%, 20%, 30%, and 50% of users receive the green highlight.

When the flag serves green, navigation applies a random 0–1000 ms latency delay and
may (5% chance) render an incorrect highlight color.
"""

from __future__ import annotations

import argparse
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
from guarded_behavior import (  # noqa: E402
    apply_latency_delay,
    exercise_session,
    is_flag_enabled,
    navigation_display_color,
    rng_for,
    sample_latency_ms,
)
from highlight_eval import FLAG_HIGHLIGHT, build_context, evaluate_highlight  # noqa: E402

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")

APP_BANNER = "15-guarded-rollout[python-console]"

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
        print("Warning: LD_SDK_KEY not set — highlight defaults to none.", flush=True)
        return False
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()
    if not wait_for_ld(_ld_client):
        print("Warning: LaunchDarkly SDK did not initialize — highlight defaults to none.", flush=True)
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
    label = str(flags["colorLabel"])
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
    display_color: str,
) -> None:
    stdscr.clear()
    stdscr.bkgd(" ", curses.color_pair(6))
    prev_text = format_pos(*previous) if previous else "—"
    line = 0
    stdscr.addstr(line, 0, APP_BANNER)
    line += 1
    draw_name_line(stdscr, line, username, flags)
    line += 1
    stdscr.addstr(line, 0, f"Flag value: {flags['flagValue']}")
    line += 1
    stdscr.addstr(line, 0, f"Current position: {format_pos(row, col)}")
    line += 1
    stdscr.addstr(line, 0, f"Previous position: {prev_text}")
    line += 2
    stdscr.addstr(line, 0, "Use arrow keys or WASD to move (L to logout, Q to quit).")
    line += 1
    stdscr.addstr(line, 0, "Toggle the flag in LaunchDarkly — changes appear within ~1s.")
    if is_flag_enabled(str(flags["highlightColor"])):
        line += 1
        stdscr.addstr(line, 0, "Guardrails active: random nav latency + occasional color errors.")

    selected_color = display_color if is_flag_enabled(str(flags["highlightColor"])) else "none"
    cell_color = selected_color if selected_color != "none" else "none"

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
    nav_rng = rng_for(username)

    try:
        while True:
            flags = evaluate_highlight(_ld_client, username)
            expected = str(flags["highlightColor"])
            display_color = expected if not is_flag_enabled(expected) else expected
            draw_screen(stdscr, username, row, col, previous, flags, display_color)
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
            if not moved:
                continue

            if is_flag_enabled(expected):
                apply_latency_delay(sample_latency_ms(nav_rng))
                display_color, _ = navigation_display_color(expected, nav_rng)
            else:
                display_color = expected

            previous = (row, col)
            row, col = new_row, new_col
            draw_screen(stdscr, username, row, col, previous, flags, display_color)
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
            context = build_context(username)
            diag: dict[str, object] = {
                "sdkInitialized": _ld_client is not None and _ld_client.is_initialized(),
                "context": json.loads(context.to_json_string()),
            }
            if _ld_client is not None and _ld_client.is_initialized():
                detail = _ld_client.variation_detail(FLAG_HIGHLIGHT, context, "none")
                diag["rawVariation"] = detail.value
                diag["variationIndex"] = detail.variation_index
                diag["reason"] = detail.reason
            diag["result"] = evaluate_highlight(_ld_client, username)
            print(json.dumps(diag, indent=2))
        else:
            print(json.dumps(evaluate_highlight(_ld_client, username)))
    finally:
        if _ld_client is not None:
            _ld_client.close()


def exercise_once(username: str, *, skip_navigation: bool = False) -> None:
    init_launchdarkly()
    try:
        flags = evaluate_highlight(_ld_client, username)
        result = exercise_session(
            flags, skip_navigation=skip_navigation, client=_ld_client
        )
        print(json.dumps(result))
    finally:
        if _ld_client is not None:
            _ld_client.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guarded rollout grid navigator")
    parser.add_argument("--evaluate-once", metavar="USERNAME")
    parser.add_argument("--exercise-once", metavar="USERNAME")
    parser.add_argument("--skip-navigation", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    if args.exercise_once:
        exercise_once(args.exercise_once, skip_navigation=args.skip_navigation)
        sys.exit(0)
    if args.evaluate_once:
        evaluate_once(args.evaluate_once, verbose=args.verbose)
        sys.exit(0)

    curses.wrapper(main)
