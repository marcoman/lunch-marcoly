#!/usr/bin/env python3
"""C++ bridge to the canonical scheduled-change SDK and REST helpers."""

import json
import os
import sys
from pathlib import Path

import ldclient
from ldclient import Config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scheduled_change import (  # noqa: E402
    api_config,
    evaluate_highlight,
    list_scheduled_changes,
    start_scheduled_change,
    stop_scheduled_change,
)


def evaluation(username: str) -> dict[str, object]:
    """Evaluate the scheduled highlight through the LaunchDarkly server SDK."""
    client = None
    sdk_key = (os.environ.get("LD_SDK_KEY") or "").strip()
    if sdk_key:
        ldclient.set_config(Config(sdk_key))
        candidate = ldclient.get()
        if candidate.is_initialized():
            client = candidate
    payload = evaluate_highlight(client, username)
    reason = payload.get("reason") or {}
    index = payload.get("variationIndex")
    if client is not None:
        client.close()
    return {
        "flagValue": payload.get("flagValue", "none"),
        "reasonKind": reason.get("kind", "UNKNOWN"),
        "variationIndex": "default" if index is None else str(index),
    }


def schedule_state() -> dict[str, object]:
    """List the earliest pending change without exposing REST credentials."""
    config = api_config()
    listed = list_scheduled_changes()
    item = (listed.get("items") or [None])[0]
    return {
        "configured": bool(config.get("configured")),
        "missing": ",".join(config.get("missing") or []),
        "pending": item is not None,
        "startedAt": (item or {}).get("createdAt") or 0,
        "executionDate": (item or {}).get("executionDate") or 0,
    }


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if command == "evaluate":
            result = evaluation(sys.argv[2] if len(sys.argv) > 2 else "")
        elif command == "list":
            result = schedule_state()
        elif command == "start":
            payload = start_scheduled_change(int(sys.argv[2]))
            change = payload["scheduledChange"]
            result = {
                "startedAt": payload["startedAt"],
                "executionDate": change["executionDate"],
                "pending": True,
            }
        elif command == "stop":
            payload = stop_scheduled_change()
            result = {"stoppedAt": payload["stoppedAt"], "pending": False}
        else:
            raise ValueError("expected evaluate, list, start, or stop")
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
