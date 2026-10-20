#!/usr/bin/env python3
"""Evaluate the team-label flag for the C++ console application."""

import json
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from team_style import evaluate_team_style  # noqa: E402


def main() -> None:
    """Evaluate with a public team attribute, omitting it for No team.

    LaunchDarkly context attributes:
    https://launchdarkly.com/docs/home/flags/context-attributes
    """
    username = sys.argv[1] if len(sys.argv) > 1 else ""
    team = sys.argv[2] if len(sys.argv) > 2 else ""
    sdk_key = os.environ.get("LD_SDK_KEY")
    client = None
    if sdk_key and username:
        ldclient.set_config(Config(sdk_key))
        candidate = ldclient.get()
        if candidate.is_initialized():
            client = candidate

    result = evaluate_team_style(client, username, team)
    print(
        json.dumps(
            {
                "team": result["team"],
                "teamLabel": result["teamLabel"],
                "style": result["style"],
                "colored": result["colored"],
                "cssColor": result["cssColor"],
            }
        )
    )
    if client is not None:
        client.close()


if __name__ == "__main__":
    main()
