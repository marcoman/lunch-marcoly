#!/usr/bin/env bash
# Locale targeting for assess, questions, good, and finalize.
#   locale = es → spanish variation
#   fallthrough → default (English instructions)
# The report node is not in this list. Its name rules stay in
# update-report-targeting.sh. Spanish on the report comes from {{ locale }}.
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-targeting

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

patch_locale() {
  local key="$1"
  echo "Loading targeting for ${key} (${LD_ENVIRONMENT_KEY})..."
  local targeting spanish_id default_id
  targeting="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${key}/targeting?env=${LD_ENVIRONMENT_KEY}")"
  # Targeting often omits variation key. Match name, key, or _ldMeta.variationKey.
  # https://launchdarkly.com/docs/api/agent-control/patch-ai-config-targeting
  spanish_id="$(echo "$targeting" | jq -r '
    .variations[]
    | select(
        (.key // "") == "spanish"
        or (.name // "") == "spanish"
        or (.value._ldMeta.variationKey // "") == "spanish"
      )
    | ._id
  ' | head -n1)"
  default_id="$(echo "$targeting" | jq -r '
    .variations[]
    | select(
        (.key // "") == "default"
        or (.name // "") == "default"
        or (.value._ldMeta.variationKey // "") == "default"
      )
    | ._id
  ' | head -n1)"
  if [[ -z "$spanish_id" || "$spanish_id" == "null" ]]; then
    echo "error: ${key} has no spanish variation" >&2
    exit 1
  fi
  if [[ -z "$default_id" || "$default_id" == "null" ]]; then
    echo "error: ${key} has no default variation" >&2
    exit 1
  fi

  api_ok PATCH "/projects/${LD_PROJECT_KEY}/ai-configs/${key}/targeting?env=${LD_ENVIRONMENT_KEY}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "$(jq -n \
      --arg env "$LD_ENVIRONMENT_KEY" \
      --arg spanish "$spanish_id" \
      --arg fallback "$default_id" \
      '{
        environmentKey: $env,
        comment: "locale es → spanish; fallthrough stays the English variation",
        instructions: [
          {
            kind: "replaceRules",
            rules: [
              {
                description: "locale es → spanish",
                variationId: $spanish,
                clauses: [{
                  contextKind: "user",
                  attribute: "locale",
                  op: "in",
                  negate: false,
                  values: ["es"]
                }]
              }
            ]
          },
          {
            kind: "updateFallthroughVariationOrRollout",
            variationId: $fallback
          }
        ]
      }')" | jq --arg env "$LD_ENVIRONMENT_KEY" '
        .environments[$env] // .environments[.environments | keys[0]]
        | {
            fallthrough,
            rules: [.rules[]? | {description, variation, clauses: [.clauses[]? | {attribute, op, values}]}]
          }
      '
}

patch_locale "$LD_NODE_ASSESS"
patch_locale "$LD_NODE_QUESTIONS"
patch_locale "$LD_NODE_GOOD"
patch_locale "$LD_NODE_FINALIZE"

echo "Done. locale=es serves the spanish variation on assess, questions, good, and finalize."
