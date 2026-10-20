#!/usr/bin/env bash
# Create the JSON display-label flag. It does not change team values or colors.
# https://launchdarkly.com/docs/sdk/features/flag-types
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

FLAG_KEY="configure-team-display-labels"

status="$(curl -sS -o /dev/null -w "%{http_code}" \
  -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
  -H "LD-API-Version: ${LD_API_VERSION}" \
  "${LD_API_HOST}/api/v2/flags/${LD_PROJECT_KEY}/${FLAG_KEY}")"
if [[ "$status" == "200" ]]; then
  echo "${FLAG_KEY} already exists; leaving it unchanged."
  exit 0
fi

echo "Creating ${FLAG_KEY}..."
api POST "/flags/${LD_PROJECT_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "configure-team-display-labels",
    "name": "Configure: team display labels",
    "description": "Words shown for red, blue, yellow, and no team. Does not change the style flag values.",
    "temporary": false,
    "tags": ["grid-navigator", "configure", "header", "json", "display-labels"],
    "variations": [
      {
        "value": {"none": "No team", "red": "Team Red", "blue": "Team Blue", "yellow": "Team Yellow"},
        "name": "Team names",
        "description": "Default words. Team values stay red, blue, and yellow."
      },
      {
        "value": {"none": "No size", "red": "Small", "blue": "Medium", "yellow": "Large"},
        "name": "Customer sizes",
        "description": "Customer vocabulary. Team values stay red, blue, and yellow."
      }
    ],
    "defaults": {"onVariation": 0, "offVariation": 0}
  }' | jq '{key,name,variations:[.variations[]|{name,value}]}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  flag_json="$(api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}?env=${LD_ENVIRONMENT_KEY}")"
  names_id="$(jq -r '.variations[] | select(.name == "Team names") | ._id' <<<"$flag_json")"
  echo "Turning ${FLAG_KEY} on with fallthrough Team names in ${LD_ENVIRONMENT_KEY}..."
  patch="$(jq -n --arg env "$LD_ENVIRONMENT_KEY" --arg names "$names_id" '{
    environmentKey: $env,
    comment: "103-flag-targeting-rules: display labels, no targeting rules",
    instructions: [
      {kind: "turnFlagOn"},
      {kind: "updateOffVariation", variationId: $names},
      {kind: "updateFallthroughVariationOrRollout", variationId: $names}
    ]
  }')"
  api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "$patch" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on,offVariation,fallthrough}"
else
  echo "LD_ENVIRONMENT_KEY not set; created variations but skipped environment state."
fi

echo "Done. Switch fallthrough to Customer sizes in Controls to relabel the UI."
