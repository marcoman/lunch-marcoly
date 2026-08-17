#!/usr/bin/env bash
# LaunchDarkly capability: AgentControl — set config fallthrough variation
# Fresh configs fall through to a disabled variation (SDK enabled=false).
# Use updateFallthroughVariationOrRollout — turnTargetingOn does not work for AI configs.
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-targeting
# https://launchdarkly.com/docs/home/agentcontrol/target

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

VARIATION_KEY="${1:-tools-anthropic}"
CONFIG_KEY="${2:-$LD_CONFIG_KEY}"

echo "Resolving targeting variation id for '${VARIATION_KEY}' on ${CONFIG_KEY} (${LD_ENVIRONMENT_KEY})..."

# Targeting variation UUIDs differ from the config detail endpoint — look them up here.
# Match by name (targeting often omits key) or by key when present.
TARGETING="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/targeting?env=${LD_ENVIRONMENT_KEY}")"
VARIATION_ID="$(
  echo "$TARGETING" | jq -r --arg k "$VARIATION_KEY" '
    .variations[]
    | select((.key // "") == $k or (.name // "") == $k)
    | ._id
  ' | head -n1
)"

if [[ -z "$VARIATION_ID" || "$VARIATION_ID" == "null" ]]; then
  echo "error: could not find variation '${VARIATION_KEY}' in targeting response" >&2
  echo "$TARGETING" | jq '[.variations[] | {key, name, _id}]' >&2
  exit 1
fi

echo "Setting fallthrough → ${VARIATION_KEY} (${VARIATION_ID})..."
api_ok PATCH "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/targeting?env=${LD_ENVIRONMENT_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg env "$LD_ENVIRONMENT_KEY" \
    --arg vid "$VARIATION_ID" \
    --arg vk "$VARIATION_KEY" \
    '{
      environmentKey: $env,
      comment: ("Default rule serves " + $vk),
      instructions: [{
        kind: "updateFallthroughVariationOrRollout",
        variationId: $vid
      }]
    }')" | jq --arg env "$LD_ENVIRONMENT_KEY" '
      .environments[$env] // .environments[.environments | keys[0]]
      | {on, fallthrough, offVariation}
    '

echo "Done. Default rule should serve ${VARIATION_KEY}."
