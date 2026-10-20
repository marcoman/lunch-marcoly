#!/usr/bin/env bash
# Create the string flag and provision team targeting rules.
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

FLAG_KEY="configure-team-label-style"

echo "Creating ${FLAG_KEY}..."
api POST "/flags/${LD_PROJECT_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "configure-team-label-style",
    "name": "Configure: team label style",
    "description": "String style selected by targeting rules on the public team context attribute.",
    "temporary": false,
    "tags": ["grid-navigator", "configure", "header", "string", "targeting-rules", "context-attributes"],
    "variations": [
      {"value": "plain", "name": "Plain", "description": "No explicit team-label color"},
      {"value": "colored-red", "name": "Colored red", "description": "Red team-label text"},
      {"value": "colored-blue", "name": "Colored blue", "description": "Blue team-label text"},
      {"value": "colored-yellow", "name": "Colored yellow", "description": "Yellow team-label text"}
    ],
    "defaults": {"onVariation": 0, "offVariation": 0}
  }' | jq '{key,name,tags,variations:[.variations[]|{value,name}]}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "Reading variation IDs..."
  flag_json="$(api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}?env=${LD_ENVIRONMENT_KEY}")"
  plain_id="$(jq -r '.variations[] | select(.value == "plain") | ._id' <<<"$flag_json")"
  red_id="$(jq -r '.variations[] | select(.value == "colored-red") | ._id' <<<"$flag_json")"
  blue_id="$(jq -r '.variations[] | select(.value == "colored-blue") | ._id' <<<"$flag_json")"
  yellow_id="$(jq -r '.variations[] | select(.value == "colored-yellow") | ._id' <<<"$flag_json")"

  echo "Turning flag on and adding red/blue/yellow rules in ${LD_ENVIRONMENT_KEY}..."
  patch="$(jq -n \
    --arg env "$LD_ENVIRONMENT_KEY" \
    --arg plain "$plain_id" --arg red "$red_id" --arg blue "$blue_id" --arg yellow "$yellow_id" \
    '{
      environmentKey: $env,
      comment: "13-flag-targeting-rules: provision team rules",
      instructions: [
        {kind: "turnFlagOn"},
        {kind: "updateOffVariation", variationId: $plain},
        {kind: "updateFallthroughVariationOrRollout", variationId: $plain},
        {kind: "addRule", description: "Team Red", clauses: [{contextKind:"user", attribute:"team", op:"in", values:["red"], negate:false}], variationId:$red},
        {kind: "addRule", description: "Team Blue", clauses: [{contextKind:"user", attribute:"team", op:"in", values:["blue"], negate:false}], variationId:$blue},
        {kind: "addRule", description: "Team Yellow", clauses: [{contextKind:"user", attribute:"team", op:"in", values:["yellow"], negate:false}], variationId:$yellow}
      ]
    }')"
  api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "$patch" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on,offVariation,fallthrough,rules}"
else
  echo "LD_ENVIRONMENT_KEY not set; created variations but skipped environment rules."
fi

echo "Done."
