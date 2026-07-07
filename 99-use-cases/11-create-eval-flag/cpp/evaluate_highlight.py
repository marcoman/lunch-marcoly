#!/usr/bin/env python3
"""Helper for the C++ implementation: evaluate highlight via highlight_eval."""

import json
import os
import sys
import time
from pathlib import Path

import ldclient
from ldclient import Config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from highlight_eval import evaluate_highlight  # noqa: E402


def wait_for_ld(client, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.is_initialized():
            return True
        time.sleep(0.05)
    return client.is_initialized()


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else ""
    if not username:
        print(json.dumps({"username": "", "flagValue": "none", "highlightColor": "none", "colorLabel": "(no-color)"}))
        return
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key:
        from highlight_eval import build_response

        print(json.dumps(build_response(username, "none")))
        return
    ldclient.set_config(Config(sdk_key))
    client = ldclient.get()
    if not wait_for_ld(client):
        from highlight_eval import build_response

        print(json.dumps(build_response(username, "none")))
        return
    try:
        print(json.dumps(evaluate_highlight(client, username)))
    finally:
        client.close()


if __name__ == "__main__":
    main()
