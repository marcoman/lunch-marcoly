#!/usr/bin/env bash
# Turn targeting on and serve the live green variation to all contexts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

flag_json="$(fetch_flag)"
green_id="$(variation_id "${flag_json}" "${LIVE_COLOR}")"

api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg environmentKey "${LD_ENVIRONMENT_KEY}" \
    --arg variationId "${green_id}" \
    '{
      environmentKey: $environmentKey,
      comment: "16-adaptive-triggers: start live variation",
      instructions: [
        {kind: "turnFlagOn"},
        {kind: "updateFallthroughVariationOrRollout", variationId: $variationId}
      ]
    }')" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough}"

echo "Live: ${FLAG_KEY} now serves ${LIVE_COLOR}. The adaptive trigger should switch it to ${SAFE_COLOR}."
