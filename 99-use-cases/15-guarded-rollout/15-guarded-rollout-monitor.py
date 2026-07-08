#!/usr/bin/env python3
"""Monitor a guarded rollout by exercising navigation guardrails every 30 seconds."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from guarded_behavior import SKIP_NAV_CHANCE  # noqa: E402
from guarded_rollout_common import (  # noqa: E402
    FLAG_KEY,
    rollout_schedule_summary,
    try_query_rollout_state,
)

TEST_NAME = "15-guarded-rollout-monitor"

DEFAULT_APP = _ROOT / "python-console" / "15-guarded-rollout.py"
DEFAULT_INTERVAL = 30
DEFAULT_BATCH_SIZE = 20


def batch_username(batch: int, index: int) -> str:
    return f"guard-probe-{batch:03d}-{index:02d}"


def run_exercise(app_cmd: list[str], username: str, skip_navigation: bool) -> dict:
    cmd = [*app_cmd, "--exercise-once", username]
    if skip_navigation:
        cmd.append("--skip-navigation")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"Exercise failed for {username}: {stderr}")
    return json.loads(result.stdout.strip())


def format_elapsed(seconds: int) -> str:
    minutes, secs = divmod(max(0, seconds), 60)
    return f"{minutes:02d}m{secs:02d}s"


def format_start_stamp(now: datetime) -> str:
    return f"[{now.strftime('%H:%M:%S')}]"


def format_batch_stamp(start: datetime, now: datetime) -> str:
    clock = now.strftime("%H:%M:%S")
    elapsed = max(0, int((now - start).total_seconds()))
    return f"[{clock} - {format_elapsed(elapsed)}]"


def format_stage_hint(state: dict[str, object] | None) -> str:
    if state is None:
        return " (stage: set LD_API_ACCESS_TOKEN to query LaunchDarkly)"
    if not state.get("on"):
        return " (stage 0: flag off, target 0%)"

    rollout_type = state.get("rolloutType")
    guarded_status = state.get("guardedStatus")
    stage = state.get("stage")
    target = state.get("stageTarget")
    configured = state.get("greenPercent")

    if rollout_type == "guarded":
        status_hint = f", status {guarded_status}" if guarded_status else ""
        if stage is None or target is None:
            return f" (guarded rollout active{status_hint})"
        configured_hint = ""
        if configured is not None:
            configured_hint = f", current {configured:.0f}%"
        return f" (guarded stage {stage}, target {target}%{configured_hint}{status_hint})"

    if rollout_type == "guarded-configured":
        return " (guarded rollout configured on fallthrough — start or resume in UI)"

    if rollout_type == "fixed" and configured == 0:
        return " (flag on, fixed none — not a guarded rollout)"

    if rollout_type == "percentage":
        if stage is None or target is None:
            return " (percentage rollout — not guarded)"
        configured_hint = ""
        if configured is not None:
            configured_hint = f", configured {configured:.0f}%"
        return (
            f" (simulated stage {stage}, target {target}%{configured_hint}"
            " — percentage rollout, not guarded)"
        )

    if stage is None or target is None:
        return " (stage: unknown fallthrough)"
    configured_hint = ""
    if configured is not None:
        configured_hint = f", configured {configured:.0f}%"
    return f" (stage {stage}, target {target}%{configured_hint})"


def format_metric_summary(results: list[dict]) -> str:
    total = len(results)
    latency_fail = sum(1 for r in results if r.get("latencyFailure"))
    error_fail = sum(1 for r in results if r.get("errorRateFailure"))
    movement_fail = sum(1 for r in results if r.get("movementFailure"))
    skipped = sum(1 for r in results if r.get("skippedNavigation"))
    green = sum(1 for r in results if r.get("highlightColor") == "green")
    return (
        f"green={green}, latencyFail={latency_fail}/{total}, "
        f"errorFail={error_fail}/{total}, movementFail={movement_fail}/{total}, "
        f"skippedNav={skipped}/{total}"
    )


def countdown(seconds: int) -> None:
    for remaining in range(seconds, 0, -1):
        print(f"\rNext evaluation in {remaining:3d}s…", end="", flush=True)
        time.sleep(1)
    print("\r" + " " * 32 + "\r", end="", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exercise guarded rollout guardrails every 30 seconds",
    )
    parser.add_argument(
        "--app-cmd",
        nargs=argparse.REMAINDER,
        default=[sys.executable, str(DEFAULT_APP)],
        help="Command prefix for --exercise-once (default: python-console app)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help="Seconds between batches (default: 30)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Exercises per batch (default: 20)",
    )
    parser.add_argument(
        "--batches",
        type=int,
        default=0,
        help="Stop after N batches (default: run until Ctrl+C)",
    )
    args = parser.parse_args()

    app_cmd = args.app_cmd
    if app_cmd and app_cmd[0] == "--":
        app_cmd = app_cmd[1:]

    start_time = datetime.now()
    batch_rng = random.Random()

    print(f"Test: {TEST_NAME}")
    print(f"Flag: {FLAG_KEY}")
    print()
    print(rollout_schedule_summary())
    print()
    print("Guardrail metrics (when flag serves green):")
    print("  Latency — nav delay 0–1000 ms; fail if >10% of moves exceed 200 ms")
    print("  Error rate — 5% random wrong color; fail if any error (0% tolerance)")
    print("  Movement — 5 navigations per test; 5% of tests skip navigation")
    print()
    print(
        f"Monitoring every {args.interval}s — {args.batch_size} exercises per batch."
    )
    print("Press Ctrl+C to stop.")
    print(format_start_stamp(start_time))
    print()

    batch_num = 0
    try:
        while True:
            batch_num += 1
            results: list[dict] = []
            for i in range(args.batch_size):
                skip = batch_rng.random() < SKIP_NAV_CHANCE
                results.append(
                    run_exercise(app_cmd, batch_username(batch_num, i), skip)
                )

            now = datetime.now()
            state = try_query_rollout_state()
            stamp = format_batch_stamp(start_time, now)
            print(
                f"{stamp} batch {batch_num:3d}: {format_metric_summary(results)}"
                f"{format_stage_hint(state)}"
            )

            if args.batches and batch_num >= args.batches:
                break
            countdown(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
