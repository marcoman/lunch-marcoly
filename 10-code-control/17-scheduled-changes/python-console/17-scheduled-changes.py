#!/usr/bin/env python3
"""Console grid navigator for LaunchDarkly scheduled flag changes."""

from __future__ import annotations

import curses
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import ldclient
from ldclient import Config
from ldclient.client import LDClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scheduled_change import (  # noqa: E402
    api_config,
    evaluate_highlight,
    list_scheduled_changes,
    start_scheduled_change,
    stop_scheduled_change,
)

# LaunchDarkly: scheduled flag changes — the server SDK re-evaluates; the
# REST API owns executionDate. https://launchdarkly.com/docs/home/flags/scheduled-changes

ROWS = ("t", "m", "b")
COLS = ("l", "m", "r")
DELAYS = (1, 2, 5, 10)
APP_BANNER = "17-scheduled-changes[python-console]"
GREEN_PAIR = 5
INK_PAIR = 7

_ld_client: LDClient | None = None


def init_launchdarkly() -> None:
    """Initialize one SDK client; scheduled changes alter its flag remotely."""
    global _ld_client
    sdk_key = (os.environ.get("LD_SDK_KEY") or "").strip()
    if not sdk_key:
        return
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()


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


def clock_ms(ms: int) -> str:
    seconds = max(0, ms) // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


def now_ms() -> int:
    return int(time.time() * 1000)


def wall(ms: int | None) -> str:
    if not ms:
        return "—"
    return datetime.fromtimestamp(ms / 1000).strftime("%H:%M:%S")


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


def status_line(
    *,
    pending: dict[str, Any] | None,
    started_at: int | None,
    stopped_at: int | None,
    observed_at: int | None,
    execution_date: int | None,
    green: bool,
) -> tuple[str, str]:
    if pending:
        return (
            "PENDING · LaunchDarkly will turn the flag on",
            f"Scheduled wall time: {wall(execution_date)}",
        )
    if stopped_at:
        elapsed = (
            f" after {clock_ms(stopped_at - started_at)} elapsed"
            if started_at
            else ""
        )
        return (
            "STOPPED · pending change cancelled, flag off",
            f"Stopped at {wall(stopped_at)}{elapsed}.",
        )
    if green and started_at:
        observed = (
            f"; green first observed here at {clock_ms(observed_at - started_at)}"
            if observed_at
            else ""
        )
        return (
            "APPLIED · SDK now serves green",
            f"Scheduled for {wall(execution_date)}{observed}.",
        )
    return ("No pending change.", "G starts a schedule. T stops it and turns the flag off.")


def draw_screen(
    stdscr: curses.window,
    username: str,
    row: int,
    col: int,
    previous: tuple[int, int] | None,
    flags: dict[str, Any],
    delay: int,
    started_at: int | None,
    stopped_at: int | None,
    observed_at: int | None,
    execution_date: int | None,
    pending: dict[str, Any] | None,
    rest_ok: bool,
    error: str,
) -> None:
    stdscr.clear()
    stdscr.bkgd(" ", curses.color_pair(INK_PAIR))
    color = str(flags.get("highlightColor") or "none")
    reason = flags.get("reason") or {}
    reason_kind = str(reason.get("kind") or "UNKNOWN")
    variation = flags.get("variationIndex")
    variation_text = "default" if variation is None else str(variation)
    end = stopped_at or now_ms()
    elapsed = clock_ms(end - started_at) if started_at else "0:00"
    status, when = status_line(
        pending=pending,
        started_at=started_at,
        stopped_at=stopped_at,
        observed_at=observed_at,
        execution_date=execution_date,
        green=color == "green",
    )
    rest = (
        "REST configured"
        if rest_ok
        else "REST disabled — set LD_API_ACCESS_TOKEN, LD_PROJECT_KEY, LD_ENVIRONMENT_KEY"
    )

    put(stdscr, 0, 0, APP_BANNER)
    put(stdscr, 1, 0, "Name: ")
    put(stdscr, 1, 6, username, cell_attr(color))
    prev_text = format_pos(*previous) if previous else "—"
    put(stdscr, 2, 0, f"Current: {format_pos(row, col)}   Previous: {prev_text}")
    put(
        stdscr,
        3,
        0,
        f"Flag value: {flags.get('flagValue')}   reason: {reason_kind}   "
        f"idx: {variation_text}",
    )
    put(stdscr, 4, 0, f"Delay: {delay} min   Elapsed: {elapsed}")
    put(stdscr, 5, 0, status)
    put(stdscr, 6, 0, when)
    put(stdscr, 7, 0, rest)
    put(
        stdscr,
        8,
        0,
        "G start  T stop  M delay  1/2/5/0=10 min  arrows/WASD  L logout  Q quit",
    )
    put(
        stdscr,
        9,
        0,
        "Lag is normal: LD executes near the date, the SDK stream follows, this loop polls ~500ms.",
        curses.A_DIM,
    )
    if error:
        put(stdscr, 10, 0, error, curses.A_BOLD)

    base_y, base_x = 12, 2
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
    stdscr.refresh()


def run_grid(stdscr: curses.window, username: str) -> str:
    """Navigate and drive the scheduled-change lab from the keyboard."""
    row, col = 1, 1
    previous: tuple[int, int] | None = None
    delay_index = 0
    started_at: int | None = None
    stopped_at: int | None = None
    observed_at: int | None = None
    execution_date: int | None = None
    pending: dict[str, Any] | None = None
    error = ""
    stdscr.timeout(500)
    try:
        while True:
            flags = evaluate_highlight(_ld_client, username)
            if (
                started_at
                and not stopped_at
                and not observed_at
                and flags.get("highlightColor") == "green"
            ):
                observed_at = now_ms()
            rest = api_config()
            try:
                listed = list_scheduled_changes()
                pending = (listed.get("items") or [None])[0]
                if pending:
                    execution_date = pending.get("executionDate") or execution_date
                    started_at = started_at or pending.get("createdAt")
            except Exception:  # noqa: BLE001
                pending = None
            draw_screen(
                stdscr,
                username,
                row,
                col,
                previous,
                flags,
                DELAYS[delay_index],
                started_at,
                stopped_at,
                observed_at,
                execution_date,
                pending,
                bool(rest.get("configured")),
                error,
            )
            key = stdscr.getch()
            if key == -1:
                continue
            if key in (ord("q"), ord("Q")):
                return "quit"
            if key in (ord("l"), ord("L")):
                return "logout"
            if key in (ord("m"), ord("M")):
                delay_index = (delay_index + 1) % len(DELAYS)
                continue
            if key == ord("1"):
                delay_index = 0
                continue
            if key == ord("2"):
                delay_index = 1
                continue
            if key == ord("5"):
                delay_index = 2
                continue
            if key == ord("0"):
                delay_index = 3
                continue
            if key in (ord("g"), ord("G")):
                try:
                    result = start_scheduled_change(DELAYS[delay_index])
                    started_at = result["startedAt"]
                    execution_date = result["scheduledChange"]["executionDate"]
                    stopped_at = None
                    observed_at = None
                    pending = result["scheduledChange"]
                    error = ""
                except Exception as exc:  # noqa: BLE001
                    error = str(exc)
                continue
            if key in (ord("t"), ord("T")):
                try:
                    result = stop_scheduled_change()
                    stopped_at = result["stoppedAt"]
                    pending = None
                    error = ""
                except Exception as exc:  # noqa: BLE001
                    error = str(exc)
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
