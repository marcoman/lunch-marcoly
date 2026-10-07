#!/usr/bin/env bash
# LaunchDarkly: AgentControl targeting for the generators
# user key codegen-1b → local-1b
# user key codegen-8b → local-8b, when that variation exists
# user key codegen-haiku → claude-haiku, when that variation exists
# user key codegen-sonnet → claude-sonnet
# fallthrough → local-3b
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-targeting
# https://launchdarkly.com/docs/home/agentcontrol/target

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

echo "Loading targeting for ${LD_CONFIG_KEY} (${LD_ENVIRONMENT_KEY})..."
TARGETING="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/targeting?env=${LD_ENVIRONMENT_KEY}")"

variation_id() {
  local key="$1"
  echo "$TARGETING" | jq -r --arg k "$key" '
    .variations[]
    | select((.key // "") == $k or (.name // "") == $k)
    | ._id
  ' | head -n1
}

SMALL_ID="$(variation_id local-1b)"
LARGE_ID="$(variation_id local-3b)"
CEILING_ID="$(variation_id "$LD_MODEL_CEILING_VARIATION_KEY")"
HAIKU_ID="$(variation_id "$LD_HAIKU_VARIATION_KEY")"
CLAUDE_ID="$(variation_id "$LD_ANTHROPIC_VARIATION_KEY")"

if [[ -z "$SMALL_ID" || "$SMALL_ID" == "null" ]]; then
  echo "error: could not resolve variation id for local-1b" >&2
  exit 1
fi
if [[ -z "$LARGE_ID" || "$LARGE_ID" == "null" ]]; then
  echo "error: could not resolve variation id for local-3b" >&2
  exit 1
fi
if [[ -z "$CLAUDE_ID" || "$CLAUDE_ID" == "null" ]]; then
  echo "error: could not resolve variation id for ${LD_ANTHROPIC_VARIATION_KEY}" >&2
  echo "Add it first: ./add-claude-variation.sh" >&2
  exit 1
fi
if [[ -z "$CEILING_ID" || "$CEILING_ID" == "null" ]]; then
  echo "warning: variation ${LD_MODEL_CEILING_VARIATION_KEY} is missing. Run ./add-local-8b-variation.sh" >&2
  CEILING_ID=""
fi
if [[ -z "$HAIKU_ID" || "$HAIKU_ID" == "null" ]]; then
  echo "warning: variation ${LD_HAIKU_VARIATION_KEY} is missing. Run ./add-haiku-variation.sh" >&2
  HAIKU_ID=""
fi

echo "local-1b → ${SMALL_ID}"
if [[ -n "$CEILING_ID" ]]; then
  echo "${LD_MODEL_CEILING_VARIATION_KEY} → ${CEILING_ID}"
fi
if [[ -n "$HAIKU_ID" ]]; then
  echo "${LD_HAIKU_VARIATION_KEY} → ${HAIKU_ID}"
fi
echo "${LD_ANTHROPIC_VARIATION_KEY} → ${CLAUDE_ID}"
echo "local-3b → ${LARGE_ID} (fallthrough)"

RULES="$(jq -n --arg small "$SMALL_ID" --arg claude "$CLAUDE_ID" '
  [
    {
      description: "Context key codegen-1b → local-1b",
      variationId: $small,
      clauses: [{
        contextKind: "user",
        attribute: "key",
        op: "in",
        negate: false,
        values: ["codegen-1b"]
      }]
    },
    {
      description: "Context key codegen-sonnet → claude-sonnet",
      variationId: $claude,
      clauses: [{
        contextKind: "user",
        attribute: "key",
        op: "in",
        negate: false,
        values: ["codegen-sonnet"]
      }]
    }
  ]
')"
if [[ -n "$CEILING_ID" ]]; then
  RULES="$(jq -n --argjson rules "$RULES" --arg ceiling "$CEILING_ID" '
    $rules[:1] + [{
      description: "Context key codegen-8b → local-8b",
      variationId: $ceiling,
      clauses: [{
        contextKind: "user",
        attribute: "key",
        op: "in",
        negate: false,
        values: ["codegen-8b"]
      }]
    }] + $rules[1:]
  ')"
fi
if [[ -n "$HAIKU_ID" ]]; then
  RULES="$(jq -n --argjson rules "$RULES" --arg haiku "$HAIKU_ID" '
    $rules[:-1] + [{
      description: "Context key codegen-haiku → claude-haiku",
      variationId: $haiku,
      clauses: [{
        contextKind: "user",
        attribute: "key",
        op: "in",
        negate: false,
        values: ["codegen-haiku"]
      }]
    }] + $rules[-1:]
  ')"
fi

api_ok PATCH "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/targeting?env=${LD_ENVIRONMENT_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg env "$LD_ENVIRONMENT_KEY" \
    --arg large "$LARGE_ID" \
    --argjson rules "$RULES" \
    '{
      environmentKey: $env,
      comment: "04 terraform codegen: codegen-1b → local-1b, codegen-8b → local-8b, codegen-sonnet → claude-sonnet, fallthrough → local-3b",
      instructions: [
        { kind: "replaceRules", rules: $rules },
        { kind: "updateFallthroughVariationOrRollout", variationId: $large }
      ]
    }')" | jq --arg env "$LD_ENVIRONMENT_KEY" '
      .environments[$env] // .environments[.environments | keys[0]]
      | {
          fallthrough,
          rules: [.rules[]? | {description, variation, clauses: [.clauses[]? | {attribute, op, values}]}]
        }'

echo "Done."
