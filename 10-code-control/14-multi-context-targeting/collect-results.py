#!/usr/bin/env python3
"""Collect the 14-multi-context 2×2 (plus unmatched) and compare to expected.

Default: evaluate with the server SDK (needs LD_SDK_KEY).
Optional: --url http://127.0.0.1:8080 hits a running lab's /api/flags.

Does not encode the matrix in the app — this script is the check harness.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import ldclient
from ldclient import Config

sys.path.insert(0, str(Path(__file__).resolve().parent))
from partner import (  # noqa: E402
    EXPECTED_PARTNER,
    evaluate_partner,
    normalize_org,
    normalize_username,
)

CASES: list[tuple[str, str, bool]] = [
    (*pair, expected) for pair, expected in EXPECTED_PARTNER.items()
] + [("carol", "acme", False)]


def _fetch_http(base: str, username: str, org: str) -> dict:
    query = urllib.parse.urlencode({"username": username, "org": org})
    url = f"{base.rstrip('/')}/api/flags?{query}"
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.loads(response.read().decode())


def _sdk_client():
    sdk_key = (os.environ.get("LD_SDK_KEY") or "").strip()
    if not sdk_key:
        print("error: LD_SDK_KEY is required unless --url is set", file=sys.stderr)
        sys.exit(2)
    ldclient.set_config(Config(sdk_key))
    client = ldclient.get()
    if not client.is_initialized():
        print("error: LaunchDarkly SDK did not initialize", file=sys.stderr)
        sys.exit(2)
    return client


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect partner-badge results for the 2×2.")
    parser.add_argument(
        "--url",
        help="Lab base URL (example: http://127.0.0.1:8080). Omit to use the SDK.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table.")
    args = parser.parse_args()

    client = None
    if not args.url:
        client = _sdk_client()

    rows = []
    failed = 0
    for username, org, expected in CASES:
        try:
            if args.url:
                payload = _fetch_http(args.url, username, org)
            else:
                payload = evaluate_partner(client, username, org)
            actual = bool(payload.get("partner"))
            reason = payload.get("reason") or {}
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, json.JSONDecodeError) as exc:
            actual = None
            reason = {"kind": "ERROR", "message": str(exc)}
        ok = actual is expected
        if not ok:
            failed += 1
        rows.append({
            "username": normalize_username(username),
            "org": normalize_org(org),
            "expected": expected,
            "actual": actual,
            "ok": ok,
            "reason": reason,
        })

    if client is not None:
        client.close()

    if args.json:
        print(json.dumps({"healthy": failed == 0, "rows": rows}, indent=2))
    else:
        print("user     org      expected  actual    reason")
        print("-------- -------- --------- --------- ------------------------------")
        for row in rows:
            actual = "—" if row["actual"] is None else str(row["actual"]).lower()
            mark = "ok" if row["ok"] else "FAIL"
            kind = (row["reason"] or {}).get("kind", "")
            extra = ""
            if "rule_index" in (row["reason"] or {}):
                extra = f" rule_index={row['reason']['rule_index']}"
            print(
                f"{row['username']:<8} {row['org']:<8} "
                f"{str(row['expected']).lower():<9} {actual:<9} {mark} {kind}{extra}"
            )
        print()
        if failed:
            print(f"{failed} mismatch(es). Provision rest/create-flags.sh and keep the flag ON.")
        else:
            print("All cases matched expected partner badge.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
