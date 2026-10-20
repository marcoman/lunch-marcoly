#!/usr/bin/env bash
# Retrieve a 15-prerequisite-flags flag, including environment targeting.
# Default: both parent and child.
# https://launchdarkly.com/docs/api/feature-flags/get-feature-flag
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

summarize() {
  local key="$1"
  local query=""
  local env="${LD_ENVIRONMENT_KEY:-}"
  [[ -n "$env" ]] && query="?env=${env}"
  api GET "/flags/${LD_PROJECT_KEY}/${key}${query}" | jq --arg env "$env" '{
    key,name,description,tags,
    variations:[.variations[]|{id:._id,value,name}],
    defaults,
    environments: (
      if $env == "" then .environments
      else {($env): (.environments[$env] // {} | {on, offVariation, fallthrough, prerequisites, rules})}
      end
    )
  }'
}

if [[ $# -gt 0 ]]; then
  summarize "$1"
  exit 0
fi

summarize "$PARENT_KEY"
summarize "$CHILD_KEY"
