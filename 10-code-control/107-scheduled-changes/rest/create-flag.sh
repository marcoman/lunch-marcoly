#!/usr/bin/env bash
# Create the scheduled-change lesson flag, serve green when on, and leave off.
# Feature flags + scheduled changes:
# https://launchdarkly.com/docs/home/flags/scheduled-changes
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

status="$(api_status GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}")"
if [[ "$status" == "200" ]]; then
  echo "${FLAG_KEY} already exists — keeping its variations."
else
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
      "key": "enable-grid-selection-highlight-sched",
      "name": "Enable: grid selection highlight (scheduled)",
      "description": "17-scheduled-changes. Starts off; the lab schedules a turnFlagOn change after a selected delay.",
      "temporary": false,
      "tags": ["grid-navigator", "enable", "ui", "string", "scheduled-changes"],
      "variations": [
        {"value": "none", "name": "No highlight", "description": "X only — no color"},
        {"value": "green", "name": "Green", "description": "Green selection highlight"}
      ],
      "defaults": {"onVariation": 1, "offVariation": 0}
    }' | jq '{key,name,tags}'
fi

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  flag="$(api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}?env=${LD_ENVIRONMENT_KEY}")"
  green_id="$(jq -er '.variations[] | select(.value == "green") | ._id' <<<"$flag")"
  api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "$(jq -nc --arg env "$LD_ENVIRONMENT_KEY" --arg variation "$green_id" '{
      environmentKey: $env,
      comment: "17-scheduled-changes initial state",
      instructions: [
        {kind: "updateFallthroughVariationOrRollout", variationId: $variation},
        {kind: "turnFlagOff"}
      ]
    }')" | jq '{key,environments}'
else
  echo "warning: LD_ENVIRONMENT_KEY unset — flag created, environment not reset." >&2
fi

echo "Done."
