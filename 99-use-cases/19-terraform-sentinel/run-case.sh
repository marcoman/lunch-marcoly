#!/usr/bin/env bash
# Run one Sentinel case. Prints the policy, the flag under test, and why it
# passed or failed. Exits non-zero when Sentinel is missing or the result is unexpected.
set -euo pipefail

policy="${1:?policy name}"
expect="${2:?pass or fail}"
case_dir="${3:?case directory}"

root="$(cd "$(dirname "$0")" && pwd)"

if ! command -v sentinel >/dev/null 2>&1; then
  echo "sentinel CLI not found. Install: https://developer.hashicorp.com/sentinel/install" >&2
  exit 1
fi

if [[ "$expect" != "pass" && "$expect" != "fail" ]]; then
  echo "expected result must be pass or fail, got: $expect" >&2
  exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

cp "$root/policies/${policy}.sentinel" "$work/${policy}.sentinel"
mkdir -p "$work/test/${policy}"
cp "$case_dir/mock-tfplan-v2.sentinel" "$work/test/${policy}/mock-tfplan-v2.sentinel"

if [[ "$expect" == "pass" ]]; then
  main_value="true"
else
  main_value="false"
fi

cat >"$work/test/${policy}/case.hcl" <<EOF
mock "tfplan/v2" {
  module {
    source = "mock-tfplan-v2.sentinel"
  }
}

test {
  rules = {
    main = ${main_value}
  }
}
EOF

set +e
json="$(cd "$work" && sentinel test -json "${policy}.sentinel" 2>"$work/sentinel.err")"
status=$?
set -e

if [[ "$status" -ne 0 ]]; then
  echo "Sentinel did not accept the ${expect} case for ${policy}." >&2
  cat "$work/sentinel.err" >&2
  printf '%s\n' "$json" >&2
  exit 1
fi

python3 -c '
import json, sys
data = json.loads(sys.argv[1])
for policy in data.get("policies", {}).values():
    if policy.get("status") != "PASS":
        sys.exit(1)
    for case in (policy.get("cases") or {}).values():
        if case.get("status") != "PASS":
            sys.exit(1)
' "$json"

python3 - "$policy" "$expect" "$case_dir/mock-tfplan-v2.sentinel" <<'PY'
import re
import sys

policy, expect, path = sys.argv[1:]
text = open(path, encoding="utf-8").read()


def field(name):
    match = re.search(rf'"{name}"\s*:\s*("?)([^",\n]+)\1', text)
    return match.group(2).strip() if match else None


key = field("key") or "(unknown flag)"
variation = field("variation_type") or "(missing)"
temporary = field("temporary")
sunset = None
if re.search(r'"key"\s*:\s*"sunset"', text):
    value = re.search(r'"value"\s*:\s*\[\s*"([^"]+)"\s*\]', text)
    sunset = value.group(1) if value else "(present)"

print(f"{policy}/{expect}: {expect}")
if policy == "temporary":
    print("  Policy   boolean flags must set temporary = true")
    print(f"  Flag     {key}")
    print(f"  Saw      variation_type = {variation}, temporary = {temporary}")
    if temporary == "true":
        print("  Why      temporary is true, so this plan passes")
    else:
        print("  Why      temporary is false. LaunchDarkly allows a permanent flag; this policy does not")
elif policy == "sunset":
    print("  Policy   boolean flags must set custom property sunset to one YYYY-MM-DD value")
    print(f"  Flag     {key}")
    if sunset:
        print(f"  Saw      sunset = {sunset}")
        print("  Why      the value matches YYYY-MM-DD, so this plan passes. LaunchDarkly stores the date and does not archive the flag")
    else:
        print("  Saw      no sunset custom property")
        print("  Why      sunset is missing, so this plan fails")
else:
    print(f"  Why      policy result is {expect}")
PY
