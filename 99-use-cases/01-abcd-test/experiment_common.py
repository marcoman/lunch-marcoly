#!/usr/bin/env python3
"""Shared ABCD experiment runner — configures rollout and exercises an application."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from abcd_eval import VARIATION_VALUES

# LaunchDarkly capability: REST API semantic patch — percentage rollout
# See: https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag

FLAG_KEY = "configure-navigation-count-label"


def resolve_experiment_seed(seed_arg: int | None) -> int:
    """Return explicit seed or a random 31-bit seed for this run."""
    if seed_arg is not None:
        return seed_arg
    return secrets.randbelow(2**31)


def sanitize_salt(raw: str | None) -> str:
    if not raw:
        return ""
    return "".join(ch for ch in raw.strip() if ch.isalnum() or ch in "-_")


def trial_username(seed: int, salt: str, index: int) -> str:
    """Build a unique LaunchDarkly context key for one experiment trial."""
    parts = ["abcd-exp", str(seed)]
    if salt:
        parts.append(salt)
    parts.append(str(index))
    return "-".join(parts)


def equal_allocation(variation_count: int) -> list[int]:
    """Split 100% across variations; remainder goes to the last slot."""
    if variation_count <= 0:
        raise ValueError("variation_count must be positive")
    base = 100 // variation_count
    allocation = [base] * variation_count
    allocation[-1] = 100 - base * (variation_count - 1)
    return allocation


def parse_allocation(raw: str | None, variation_count: int) -> list[int]:
    if raw is None:
        return equal_allocation(variation_count)
    parts = [int(p.strip()) for p in raw.split(",")]
    if len(parts) != variation_count:
        raise ValueError(
            f"--experiment-allocation expects {variation_count} values, got {len(parts)}"
        )
    if sum(parts) != 100:
        raise ValueError(f"allocation must sum to 100, got {sum(parts)}")
    return parts


def api_request(method: str, path: str, body: dict | None = None) -> dict:
    api_host = os.environ.get("LD_API_HOST", "https://app.launchdarkly.com")
    token = os.environ.get("LD_API_ACCESS_TOKEN")
    project = os.environ.get("LD_PROJECT_KEY")
    if not token or not project:
        raise SystemExit("LD_API_ACCESS_TOKEN and LD_PROJECT_KEY are required")

    url = f"{api_host}/api/v2{path}"
    headers = {
        "Authorization": token,
        "LD-API-Version": os.environ.get("LD_API_VERSION", "20240415"),
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json; domain-model=launchdarkly.semanticpatch"
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"LaunchDarkly API error {exc.code}: {detail}") from exc


def fetch_flag() -> dict:
    project = os.environ["LD_PROJECT_KEY"]
    return api_request("GET", f"/flags/{project}/{FLAG_KEY}")


def require_environment_key(flag: dict) -> str:
    env_key = os.environ.get("LD_ENVIRONMENT_KEY", "").strip()
    if not env_key:
        raise SystemExit(
            "LD_ENVIRONMENT_KEY is required to configure rollout. "
            "Set it to the environment key shown in LaunchDarkly (e.g. test, production)."
        )

    environments = flag.get("environments", {})
    if env_key not in environments:
        available = ", ".join(sorted(environments.keys())) or "(none)"
        raise SystemExit(
            f"LD_ENVIRONMENT_KEY={env_key!r} was not found in project "
            f"{os.environ['LD_PROJECT_KEY']!r}.\n"
            f"Available environments: {available}\n"
            "Tip: LD_ENVIRONMENT_KEY must match the SDK key environment "
            "(Account settings → Projects → your project → Environments)."
        )
    return env_key


def fetch_variation_ids(flag: dict) -> list[tuple[str, str]]:
    variations = flag.get("variations", [])
    result: list[tuple[str, str]] = []
    for item in variations:
        value = item.get("value")
        var_id = item.get("_id")
        if var_id is not None and value is not None:
            result.append((str(value), str(var_id)))
    if not result:
        raise SystemExit("Could not read variation IDs from LaunchDarkly flag")
    return result


def apply_rollout(
    allocation: list[int],
    variation_ids: list[tuple[str, str]],
    env_key: str,
) -> None:
    project = os.environ.get("LD_PROJECT_KEY")
    if len(allocation) != len(variation_ids):
        raise ValueError("allocation length must match variation count")

    rollout_weights = {
        var_id: allocation[i] * 1000 for i, (_, var_id) in enumerate(variation_ids)
    }

    body = {
        "environmentKey": env_key,
        "comment": "ABCD experiment: configure fallthrough percentage rollout",
        "instructions": [
            {"kind": "turnFlagOn"},
            {
                "kind": "updateFallthroughVariationOrRollout",
                "rolloutContextKind": "user",
                "rolloutWeights": rollout_weights,
            },
        ],
    }
    api_request("PATCH", f"/flags/{project}/{FLAG_KEY}", body)


def run_once(app_cmd: list[str], username: str, cwd: Path | None = None) -> str:
    env = os.environ.copy()
    result = subprocess.run(
        [*app_cmd, "--evaluate-once", username],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd) if cwd else None,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"Application run failed for {username}: {stderr}")
    return result.stdout.strip()


def prompt_int(label: str, default: int) -> int:
    raw = input(f"{label} [{default}]: ").strip()
    return int(raw) if raw else default


def prompt_allocation(default: list[int]) -> list[int]:
    default_str = ",".join(str(v) for v in default)
    raw = input(f"Allocation % per variation [{default_str}]: ").strip()
    return parse_allocation(raw or None, len(default))


def prompt_str(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{label}{suffix}: ").strip()
    return raw if raw else default


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {secs}s"


def format_percentages_so_far(counts: Counter[str], completed: int) -> str:
    parts = []
    for value in VARIATION_VALUES:
        pct = counts.get(value, 0) / completed * 100
        parts.append(f"{value} {pct:.1f}%")
    for value, seen in sorted(counts.items()):
        if value not in VARIATION_VALUES:
            pct = seen / completed * 100
            parts.append(f"{value} {pct:.1f}%")
    return ", ".join(parts)


def print_progress(
    completed: int,
    total: int,
    counts: Counter[str],
    start: float,
) -> None:
    elapsed = time.perf_counter() - start
    eta = (elapsed / completed) * (total - completed) if completed else 0.0
    print(
        f"[{completed} / {total}]  "
        f"Elapsed: {format_duration(elapsed)} : "
        f"ETA: {format_duration(eta)} : "
        f"{format_percentages_so_far(counts, completed)}",
        flush=True,
    )


def print_summary(counts: Counter[str], total: int) -> None:
    print()
    print(f"{'Variation':<22} {'Count':>8} {'Pct':>8}")
    print("-" * 40)
    for value in VARIATION_VALUES:
        count = counts.get(value, 0)
        pct = (count / total * 100) if total else 0.0
        print(f"{value:<22} {count:>8} {pct:>7.1f}%")
    for value, count in sorted(counts.items()):
        if value not in VARIATION_VALUES:
            pct = (count / total * 100) if total else 0.0
            print(f"{value:<22} {count:>8} {pct:>7.1f}%")
    print("-" * 40)
    print(f"{'Total':<22} {total:>8}")


def main(app_cmd: list[str], cwd: Path | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run ABCD label experiment trials")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt to confirm or override parameters",
    )
    parser.add_argument(
        "--experiment-count",
        type=int,
        default=1000,
        help="Number of experiment trials (default: 1000)",
    )
    parser.add_argument(
        "--experiment-delay",
        type=int,
        default=1,
        help="Delay between trials in milliseconds (default: 1)",
    )
    parser.add_argument(
        "--experiment-allocation",
        type=str,
        default=None,
        help="Comma-separated %% per variation (default: equal split)",
    )
    parser.add_argument(
        "--experiment-seed",
        type=int,
        default=None,
        help="Seed for trial context keys (default: random per run)",
    )
    parser.add_argument(
        "--experiment-salt",
        type=str,
        default=None,
        help="Optional extra string mixed into each trial username for more variation",
    )
    args = parser.parse_args()

    flag = fetch_flag()
    env_key = require_environment_key(flag)
    variation_ids = fetch_variation_ids(flag)

    count = args.experiment_count
    delay_ms = args.experiment_delay
    allocation = parse_allocation(args.experiment_allocation, len(variation_ids))
    seed = resolve_experiment_seed(args.experiment_seed)
    salt = sanitize_salt(args.experiment_salt)

    if args.interactive:
        count = prompt_int("Experiment count", count)
        delay_ms = prompt_int("Delay between trials (ms)", delay_ms)
        allocation = prompt_allocation(allocation)
        seed_raw = prompt_str("Experiment seed (empty = random)", str(seed))
        seed = int(seed_raw) if seed_raw else resolve_experiment_seed(None)
        salt = sanitize_salt(prompt_str("Experiment salt (optional)", salt))
        alloc_str = ", ".join(f"{v}%" for v in allocation)
        if input(f"Run {count} trials with allocation {alloc_str}? [Y/n]: ").strip().lower() == "n":
            print("Cancelled.")
            return

    print(f"Configuring rollout in {env_key}: {allocation}")
    apply_rollout(allocation, variation_ids, env_key)

    sample_user = trial_username(seed, salt, 0)
    print(
        f"Trial contexts: {sample_user} … {trial_username(seed, salt, count - 1)} "
        f"(seed={seed}" + (f", salt={salt!r}" if salt else "") + ")"
    )

    counts: Counter[str] = Counter()
    start = time.perf_counter()
    for i in range(count):
        username = trial_username(seed, salt, i)
        label = run_once(app_cmd, username, cwd=cwd)
        counts[label] += 1
        completed = i + 1
        if completed % 10 == 0 or completed == count:
            print_progress(completed, count, counts, start)
        if delay_ms > 0 and completed < count:
            time.sleep(delay_ms / 1000.0)

    print_summary(counts, count)
