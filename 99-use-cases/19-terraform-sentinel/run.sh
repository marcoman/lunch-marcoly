#!/usr/bin/env bash
# Run every fixture. Each block names the policy, the flag in the plan, and why it passed or failed.
set -euo pipefail

root="$(cd "$(dirname "$0")" && pwd)"

echo "Four Terraform plan fixtures. Sentinel only — no LaunchDarkly API call."
echo

for case_dir in temporary/pass temporary/fail sunset/pass sunset/fail; do
  "$root/$case_dir/run.sh"
  echo
done
