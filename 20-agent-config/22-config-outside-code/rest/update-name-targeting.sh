#!/usr/bin/env bash
# Name targeting: Best Betty → tracked-anthropic; fallthrough → tracked-ollama
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-targeting

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

CONFIG_KEY="${1:-$LD_CONFIG_KEY}"

echo "Loading targeting for ${CONFIG_KEY} (${LD_ENVIRONMENT_KEY})..."
TARGETING="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/targeting?env=${LD_ENVIRONMENT_KEY}")"

variation_id() {
  local key="$1"
  echo "$TARGETING" | jq -r --arg k "$key" '
    .variations[]
    | select((.key // "") == $k or (.name // "") == $k)
    | ._id
  ' | head -n1
}

OLLAMA_ID="$(variation_id tracked-ollama)"
ANTHROPIC_ID="$(variation_id tracked-anthropic)"

if [[ -z "$OLLAMA_ID" || "$OLLAMA_ID" == "null" ]]; then
  echo "error: could not resolve variation id for tracked-ollama" >&2
  exit 1
fi
if [[ -z "$ANTHROPIC_ID" || "$ANTHROPIC_ID" == "null" ]]; then
  echo "error: could not resolve variation id for tracked-anthropic" >&2
  exit 1
fi

echo "tracked-ollama     → ${OLLAMA_ID}"
echo "tracked-anthropic  → ${ANTHROPIC_ID}"
echo "Applying Best Betty name rule + fallthrough → tracked-ollama..."

api_ok PATCH "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/targeting?env=${LD_ENVIRONMENT_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg env "$LD_ENVIRONMENT_KEY" \
    --arg ollama "$OLLAMA_ID" \
    --arg anthropic "$ANTHROPIC_ID" \
    '{
      environmentKey: $env,
      comment: "Best Betty → tracked-anthropic; default tracked-ollama",
      instructions: [
        {
          kind: "replaceRules",
          rules: [
            {
              description: "Best Betty → tracked-anthropic",
              variationId: $anthropic,
              clauses: [{
                contextKind: "user",
                attribute: "name",
                op: "in",
                negate: false,
                values: ["Best Betty"]
              }]
            }
          ]
        },
        {
          kind: "updateFallthroughVariationOrRollout",
          variationId: $ollama
        }
      ]
    }')" | jq --arg env "$LD_ENVIRONMENT_KEY" '
      .environments[$env] // .environments[.environments | keys[0]]
      | {
          fallthrough,
          rules: [.rules[]? | {
            description,
            variation,
            clauses: [.clauses[]? | {attribute, op, values}]
          }]
        }
    '

echo "Done."
echo "  Best Betty        → tracked-anthropic (claude-sonnet-5)"
echo "  Default / Amelia  → tracked-ollama (llama3.2:1b)"
