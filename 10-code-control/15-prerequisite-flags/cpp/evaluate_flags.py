#!/usr/bin/env python3
"""Helper for the C++ console: evaluate prerequisite flags via the Python SDK."""

import json
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from prerequisite import evaluate_prerequisite_flags  # noqa: E402


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else ""
    if not username:
        print(
            json.dumps(
                {
                    "highlightColor": "none",
                    "showMoveCount": False,
                    "parentValue": "none",
                    "parentReason": "OFFLINE",
                    "childReason": "OFFLINE",
                    "prerequisiteKey": "",
                }
            )
        )
        return
    sdk_key = os.environ.get("LD_SDK_KEY")
    client = None
    if sdk_key and username:
        ldclient.set_config(Config(sdk_key))
        client = ldclient.get()
        if not client.is_initialized():
            client = None
    payload = evaluate_prerequisite_flags(client, username)
    parent_reason = payload["parent"]["reason"]
    child_reason = payload["child"]["reason"]
    print(
        json.dumps(
            {
                "highlightColor": payload["highlightColor"],
                "showMoveCount": payload["showMoveCount"],
                "parentValue": payload["parent"]["value"],
                "parentReason": parent_reason.get("kind", "UNKNOWN"),
                "childReason": child_reason.get("kind", "UNKNOWN"),
                "prerequisiteKey": child_reason.get("prerequisiteKey") or "",
            },
            ensure_ascii=False,
        )
    )
    if client is not None:
        client.close()


if __name__ == "__main__":
    main()
