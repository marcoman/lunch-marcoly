#!/usr/bin/env python3
"""Evaluate the partner-badge flag for the C++ console application."""

import json
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from partner import evaluate_partner  # noqa: E402


def main() -> None:
    """Evaluate show-partner-org-badge with a user + organization multi-context.

    LaunchDarkly multi-contexts:
    https://launchdarkly.com/docs/home/flags/multi-contexts
    """
    username = sys.argv[1] if len(sys.argv) > 1 else ""
    org = sys.argv[2] if len(sys.argv) > 2 else "acme"
    sdk_key = os.environ.get("LD_SDK_KEY")
    client = None
    if sdk_key and username:
        ldclient.set_config(Config(sdk_key))
        candidate = ldclient.get()
        if candidate.is_initialized():
            client = candidate

    result = evaluate_partner(client, username, org)
    print(
        json.dumps(
            {
                "username": result["username"],
                "org": result["org"],
                "orgLabel": result["orgLabel"],
                "partner": result["partner"],
            }
        )
    )
    if client is not None:
        client.close()


if __name__ == "__main__":
    main()
