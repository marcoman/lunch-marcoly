#!/usr/bin/env python3
"""Helper for the C++ implementation: evaluate flags via the Python server SDK."""

import json
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flag_variations import evaluate_flags  # noqa: E402
from host_os import HOST_OS_ATTR, detect_host_os  # noqa: E402


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else ""
    sdk_key = os.environ.get("LD_SDK_KEY")
    host_os = detect_host_os()
    if not sdk_key or not username:
        print(
            json.dumps(
                {
                    "countLabel": "Count",
                    "luckyNumber": 0,
                    "maxMoves": 100,
                    "osEmoji": "",
                },
                ensure_ascii=False,
            )
        )
        return
    ldclient.set_config(Config(sdk_key, private_attributes=[HOST_OS_ATTR]))
    client = ldclient.get()
    if not client.is_initialized():
        print(
            json.dumps(
                {
                    "countLabel": "Count",
                    "luckyNumber": 0,
                    "maxMoves": 100,
                    "osEmoji": "",
                },
                ensure_ascii=False,
            )
        )
        return
    result = evaluate_flags(client, username, host_os)
    print(json.dumps(result, ensure_ascii=False))
    client.close()


if __name__ == "__main__":
    main()
