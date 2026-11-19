#!/usr/bin/env bash
# Read the approval lab flag.
# https://launchdarkly.com/docs/api/feature-flags/get-feature-flag
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

query=""
env="${LD_ENVIRONMENT_KEY:-}"
[[ -n "$env" ]] && query="?env=${env}"
api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}${query}" | jq --arg env "$env" '{
  key, name,
  environments: (
    if $env == "" then .environments
    else {($env): (.environments[$env] // {} | {on})}
    end
  )
}'
