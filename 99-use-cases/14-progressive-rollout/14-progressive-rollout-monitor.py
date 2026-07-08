#!/usr/bin/env python3
"""Monitor a progressive rollout by sampling SDK evaluations every 30 seconds."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from progressive_rollout_common import (  # noqa: E402
    BASELINE_COLOR,
    FLAG_KEY,
    ROLLOUT_COLOR,
    rollout_schedule_summary,
    try_query_rollout_state,
)

TEST_NAME = "14-progressive-rollout-monitor"

DEFAULT_APP = _ROOT / "python-console" / "14-progressive-rollout.py"
DEFAULT_INTERVAL = 30
DEFAULT_BATCH_SIZE = 20


def batch_username(batch: int, index: int) -> str:
    return f"rollout-probe-{batch:03d}-{index:02d}"


def run_evaluation(app_cmd: list[str], username: str) -> str:
    result = subprocess.run(
        [*app_cmd, "--evaluate-once", username],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"Evaluation failed for {username}: {stderr}")
    payload = json.loads(result.stdout.strip())
    raw = str(payload.get("flagValue", payload.get("highlightColor", BASELINE_COLOR))).strip().lower()
    if raw in (ROLLOUT_COLOR, BASELINE_COLOR):
        return raw
    if raw in ("", "null", "undefined"):
        return BASELINE_COLOR
    return raw


def format_counts(counts: Counter[str], total: int) -> str:
    green = counts.get(ROLLOUT_COLOR, 0)
    none = counts.get(BASELINE_COLOR, 0)
    other = total - green - none
    parts = [f"{ROLLOUT_COLOR}={green}", f"none={none}"]
    if other:
        parts.append(f"other={other}")
    observed = (green / total * 100) if total else 0.0
    parts.append(f"observed {observed:.0f}%")
    return ", ".join(parts)


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
    stage = state.get("stage")
    target = state.get("stageTarget")
    configured = state.get("greenPercent")

    if rollout_type == "guarded":
        return " (guarded rollout detected — use 15-guarded-rollout, not progressive)"

    if rollout_type == "progressive":
        if stage is None or target is None:
            return " (progressive rollout active)"
        configured_hint = ""
        if configured is not None:
            configured_hint = f", current {configured:.0f}%"
        return f" (progressive stage {stage}, target {target}%{configured_hint})"

    if rollout_type == "percentage":
        if stage is None or target is None:
            return " (simulated percentage rollout via REST)"
        configured_hint = ""
        if configured is not None:
            configured_hint = f", configured {configured:.0f}%"
        return (
            f" (simulated stage {stage}, target {target}%{configured_hint}"
            " — REST percentage, not UI progressive)"
        )

    if rollout_type == "fixed" and configured == 0:
        return " (flag on, fixed none — no rollout)"

    if stage is None or target is None:
        return " (stage: unknown fallthrough)"
    configured_hint = ""
    if configured is not None:
        configured_hint = f", configured {configured:.0f}%"
    return f" (stage {stage}, target {target}%{configured_hint})"


def countdown(seconds: int) -> None:
    for remaining in range(seconds, 0, -1):
        print(f"\rNext evaluation in {remaining:3d}s…", end="", flush=True)
        time.sleep(1)
    print("\r" + " " * 32 + "\r", end="", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample progressive rollout results every 30 seconds",
    )
    parser.add_argument(
        "--app-cmd",
        nargs=argparse.REMAINDER,
        default=[sys.executable, str(DEFAULT_APP)],
        help="Command prefix for --evaluate-once (default: python-console app)",
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
        help="Evaluations per batch (default: 20)",
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

    print(f"Test: {TEST_NAME}")
    print(f"Flag: {FLAG_KEY}")
    print()
    print(rollout_schedule_summary())
    print()
    print(
        f"Monitoring every {args.interval}s — {args.batch_size} evaluations per batch "
        f"({ROLLOUT_COLOR} highlight vs none)."
    )
    print("Press Ctrl+C to stop.")
    print(format_start_stamp(start_time))
    print()

    batch_num = 0
    try:
        while True:
            batch_num += 1
            counts: Counter[str] = Counter()
            for i in range(args.batch_size):
                color = run_evaluation(app_cmd, batch_username(batch_num, i))
                counts[color] += 1

            now = datetime.now()
            state = try_query_rollout_state()
            stamp = format_batch_stamp(start_time, now)
            print(
                f"{stamp} batch {batch_num:3d}: {format_counts(counts, args.batch_size)}"
                f"{format_stage_hint(state)}"
            )

            if args.batches and batch_num >= args.batches:
                break
            countdown(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
