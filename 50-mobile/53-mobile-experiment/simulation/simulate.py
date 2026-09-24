#!/usr/bin/env python3
"""Generate clearly labeled synthetic experiment exposure and conversion events."""

from __future__ import annotations

import argparse
import os
import random
import sys
import time

from ldclient import Config
from ldclient.client import LDClient
from ldclient.context import Context

FLAG_KEY = "acme-mobile-onboarding-v2"
EVENT_KEY = "mobile_onboarding_completed"


def probability(value: str) -> float:
    """Parse a probability in the inclusive range 0..1."""
    number = float(value)
    if not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("must be between 0 and 1")
    return number


def positive_int(value: str) -> int:
    """Parse a positive integer."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def nonnegative_float(value: str) -> float:
    """Parse a non-negative delay."""
    number = float(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be at least 0")
    return number


def parse_args() -> argparse.Namespace:
    """Define controls for deterministic population and probabilistic conversion."""
    parser = argparse.ArgumentParser(
        description=(
            "Send synthetic mobile flag evaluations and optional onboarding "
            "conversion events to a dedicated LaunchDarkly environment."
        )
    )
    parser.add_argument("--count", type=positive_int, default=100)
    parser.add_argument("--seed", type=int, default=53)
    parser.add_argument("--control-probability", type=probability, default=0.30)
    parser.add_argument("--treatment-probability", type=probability, default=0.45)
    parser.add_argument(
        "--delay",
        type=nonnegative_float,
        default=0.0,
        help="seconds to wait after each synthetic user",
    )
    parser.add_argument("--app-version", default="1.0.0-synthetic")
    return parser.parse_args()


def build_context(seed: int, index: int, app_version: str) -> Context:
    """Build a stable user context with mobile analysis attributes."""
    platform = "android" if index % 2 == 0 else "ios"
    return (
        Context.builder(f"synthetic-{seed}-{index:06d}")
        .kind("user")
        .set("platform", platform)
        .set("app-version", app_version)
        .set("synthetic", True)
        .build()
    )


def main() -> int:
    """Evaluate before tracking so every conversion has an exposure event."""
    args = parse_args()
    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    if not sdk_key:
        print("error: LD_SDK_KEY is required", file=sys.stderr)
        return 2

    print(
        "WARNING: sending synthetic traffic. Use a dedicated LaunchDarkly "
        "environment; these events affect experiment results.",
        file=sys.stderr,
    )
    rng = random.Random(args.seed)
    client = LDClient(Config(sdk_key))
    if not client.is_initialized():
        print("error: LaunchDarkly server SDK did not initialize", file=sys.stderr)
        client.close()
        return 1

    counts = {
        "control_exposures": 0,
        "treatment_exposures": 0,
        "control_conversions": 0,
        "treatment_conversions": 0,
    }
    try:
        for index in range(args.count):
            context = build_context(args.seed, index, args.app_version)
            treatment = bool(client.variation(FLAG_KEY, context, False))
            arm = "treatment" if treatment else "control"
            counts[f"{arm}_exposures"] += 1
            chance = (
                args.treatment_probability
                if treatment
                else args.control_probability
            )
            if rng.random() < chance:
                client.track(EVENT_KEY, context)
                counts[f"{arm}_conversions"] += 1
            if args.delay:
                time.sleep(args.delay)
        client.flush()
    finally:
        client.close()

    print(f"seed={args.seed} users={args.count}")
    for key, value in counts.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
