#!/usr/bin/env bash
# Print the platform clause values for enable-mobile-platform-rollout.
# https://launchdarkly.com/docs/api/feature-flags/get-feature-flag

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

FLAG_KEY="enable-mobile-platform-rollout"
project="$(jq -nr --arg v "$LD_PROJECT_KEY" '$v|@uri')"
flag="$(jq -nr --arg v "$FLAG_KEY" '$v|@uri')"
environment="$(jq -nr --arg v "$LD_ENVIRONMENT_KEY" '$v|@uri')"

flag_json="$(api_ok GET "/flags/${project}/${flag}?env=${environment}")"
on="$(jq -r --arg env "$LD_ENVIRONMENT_KEY" '.environments[$env].on' <<<"$flag_json")"
values="$(jq -r --arg env "$LD_ENVIRONMENT_KEY" '
  [.environments[$env].rules[]?.clauses[]?
    | select(.attribute == "platform" and .op == "in")
    | .values[]]
  | unique
  | if length == 0 then "(none)" else join(", ") end
' <<<"$flag_json")"

echo "flag: ${FLAG_KEY}"
echo "environment: ${LD_ENVIRONMENT_KEY}"
echo "on: ${on}"
echo "platform values: ${values}"
