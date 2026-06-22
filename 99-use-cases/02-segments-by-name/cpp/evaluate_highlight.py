#!/usr/bin/env python3
"""Helper for the C++ implementation: evaluate highlight via segment_style."""

import json
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from segment_context import resolve_segment_info  # noqa: E402
from segment_style import build_flag_response, evaluate_highlight  # noqa: E402


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else ""
    info = resolve_segment_info(username) if username else resolve_segment_info("anonymous")
    sdk_key = os.environ.get("LD_SDK_KEY")
    if not sdk_key or not username:
        print(json.dumps(build_flag_response(username, "none", info), ensure_ascii=False))
        return
    ldclient.set_config(Config(sdk_key))
    client = ldclient.get()
    if not client.is_initialized():
        print(json.dumps(build_flag_response(username, "none", info), ensure_ascii=False))
        return
    try:
        result = evaluate_highlight(client, username)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        client.close()


if __name__ == "__main__":
    main()
