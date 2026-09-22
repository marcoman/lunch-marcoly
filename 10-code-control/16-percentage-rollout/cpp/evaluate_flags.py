#!/usr/bin/env python3
"""Helper for the C++ console: evaluate the static rollout via the Python SDK."""

import json
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rollout import evaluate_rollout  # noqa: E402


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else ""
    if not username:
        print(
            json.dumps(
                {
                    "flagValue": "none",
                    "highlightColor": "none",
                    "reasonKind": "ERROR",
                    "variationIndex": "default",
                }
            )
        )
        return
    sdk_key = os.environ.get("LD_SDK_KEY")
    client = None
    if sdk_key:
        ldclient.set_config(Config(sdk_key))
        client = ldclient.get()
        if not client.is_initialized():
            client = None
    payload = evaluate_rollout(client, username)
    reason = payload.get("reason") or {}
    index = payload.get("variationIndex")
    print(
        json.dumps(
            {
                "flagValue": payload.get("flagValue", "none"),
                "highlightColor": payload.get("highlightColor", "none"),
                "reasonKind": reason.get("kind", "UNKNOWN"),
                "variationIndex": "default" if index is None else str(index),
            },
            ensure_ascii=False,
        )
    )
    if client is not None:
        client.close()


if __name__ == "__main__":
    main()
