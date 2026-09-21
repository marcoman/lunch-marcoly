#!/usr/bin/env bash
# Create the dedicated 16-percentage-rollout flag, then configure 30/70.
# Feature flags — percentage rollout on the default rule.
# https://launchdarkly.com/docs/home/flags/rollouts
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

status="$(api_status GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}")"
if [[ "$status" == "200" ]]; then
  echo "${FLAG_KEY} already exists — keeping its variations."
else
  echo "Creating ${FLAG_KEY}..."
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
      "key": "enable-grid-selection-highlight-pct",
      "name": "Enable: grid selection highlight (pct)",
      "description": "16-percentage-rollout. Static 30/70 green/none rollout on username context key. Dedicated key so 11 stays independent. Not a progressive rollout.",
      "temporary": false,
      "tags": ["grid-navigator", "enable", "ui", "string", "percentage-rollout"],
      "variations": [
        {"value": "none", "name": "No highlight", "description": "X only — no color"},
        {"value": "green", "name": "Green", "description": "Green selection highlight"}
      ],
      "defaults": {"onVariation": 1, "offVariation": 0}
    }' | jq '{key,name,tags,variations:[.variations[]|{id:._id,value}]}'
fi

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  "${SCRIPT_DIR}/set-rollout-percent.sh" 30
else
  echo "warning: LD_ENVIRONMENT_KEY unset — flag created, rollout not configured." >&2
fi

echo "Done."
