#!/usr/bin/env bash
# Name targeting for equity-briefing-graph-report only.
#   Conservative Charlie → concise-skeptic
#   Thoughtless Toby     → reckless-hype
#   Fallthrough (Amelia) → baseline-analyst
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-targeting

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

CONFIG_KEY="${1:-$LD_NODE_REPORT}"

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

BASELINE_ID="$(variation_id baseline-analyst)"
SKEPTIC_ID="$(variation_id concise-skeptic)"
RECKLESS_ID="$(variation_id reckless-hype)"

if [[ -z "$BASELINE_ID" || "$BASELINE_ID" == "null" ]]; then
  echo "error: could not resolve variation id for baseline-analyst" >&2
  exit 1
fi
if [[ -z "$SKEPTIC_ID" || "$SKEPTIC_ID" == "null" ]]; then
  echo "error: could not resolve variation id for concise-skeptic" >&2
  exit 1
fi
if [[ -z "$RECKLESS_ID" || "$RECKLESS_ID" == "null" ]]; then
  echo "error: could not resolve variation id for reckless-hype" >&2
  exit 1
fi

echo "baseline-analyst → ${BASELINE_ID}"
echo "concise-skeptic  → ${SKEPTIC_ID}"
echo "reckless-hype    → ${RECKLESS_ID}"

api_ok PATCH "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/targeting?env=${LD_ENVIRONMENT_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg env "$LD_ENVIRONMENT_KEY" \
    --arg baseline "$BASELINE_ID" \
    --arg skeptic "$SKEPTIC_ID" \
    --arg reckless "$RECKLESS_ID" \
    '{
      environmentKey: $env,
      comment: "Report node: Charlie→skeptic, Toby→reckless; fallthrough baseline",
      instructions: [
        {
          kind: "replaceRules",
          rules: [
            {
              description: "Conservative Charlie → concise-skeptic",
              variationId: $skeptic,
              clauses: [{
                contextKind: "user",
                attribute: "name",
                op: "in",
                negate: false,
                values: ["Conservative Charlie"]
              }]
            },
            {
              description: "Thoughtless Toby → reckless-hype",
              variationId: $reckless,
              clauses: [{
                contextKind: "user",
                attribute: "name",
                op: "in",
                negate: false,
                values: ["Thoughtless Toby"]
              }]
            }
          ]
        },
        {
          kind: "updateFallthroughVariationOrRollout",
          variationId: $baseline
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
echo "  Conservative Charlie → concise-skeptic"
echo "  Thoughtless Toby     → reckless-hype"
echo "  Default (Amelia)     → baseline-analyst"
