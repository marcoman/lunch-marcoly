#!/usr/bin/env bash
# Show flag variations and the configured static rollout.
# https://launchdarkly.com/docs/api/feature-flags/get-feature-flag
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

query=""
[[ -n "${LD_ENVIRONMENT_KEY:-}" ]] && query="?env=${LD_ENVIRONMENT_KEY}"

api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}${query}" \
  | jq --arg env "${LD_ENVIRONMENT_KEY:-}" '{
      key,name,description,tags,
      variations:[.variations[]|{id:._id,value,name}],
      environment: (
        if $env == "" then null
        else .environments[$env] | {on,offVariation,fallthrough}
        end
      )
    }'
