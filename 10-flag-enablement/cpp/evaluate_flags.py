#!/usr/bin/env python3
"""Helper for the C++ implementation: evaluate flags via the Python server SDK."""

import json
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from highlight_style import (  # noqa: E402
    FLAG_CONTEXT,
    FLAG_COUNT,
    FLAG_HIGHLIGHT,
    build_flag_response,
)
from host_os import (  # noqa: E402
    FLAG_OS_EMOJI,
    HOST_OS_ATTR,
    build_evaluation_context,
    detect_host_os,
)


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else ""
    sdk_key = os.environ.get("LD_SDK_KEY")
    host_os = detect_host_os()
    if not sdk_key or not username:
        print(json.dumps(build_flag_response(username, False, False, False, False, host_os)))
        return
    ldclient.set_config(Config(sdk_key, private_attributes=[HOST_OS_ATTR]))
    client = ldclient.get()
    if not client.is_initialized():
        print(json.dumps(build_flag_response(username, False, False, False, False, host_os)))
        return
    context, host_os = build_evaluation_context(username)
    result = build_flag_response(
        username,
        bool(client.variation(FLAG_HIGHLIGHT, context, False)),
        bool(client.variation(FLAG_CONTEXT, context, False)),
        bool(client.variation(FLAG_COUNT, context, False)),
        bool(client.variation(FLAG_OS_EMOJI, context, False)),
        host_os,
    )
    print(json.dumps(result))
    client.close()


if __name__ == "__main__":
    main()
