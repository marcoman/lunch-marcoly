#!/usr/bin/env bash
# LaunchDarkly: AgentControl — one judge config, Sonnet, temperature 0
# Scores a generated main.tf. The app calls Anthropic and records the score.
# https://launchdarkly.com/docs/home/agentcontrol/judges
# https://launchdarkly.com/docs/api/agent-control/post-ai-config

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"
KEY="$LD_JUDGE_KEY"

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${KEY}")"
if [[ "$STATUS" == "200" ]]; then
  echo "Judge ${KEY} already exists — skipping create."
  api GET "/projects/${LD_PROJECT_KEY}/ai-configs/${KEY}" \
    | jq '{key, name, mode, evaluationMetricKey}'
  exit 0
fi

echo "==> Judge ${KEY} → ${LD_JUDGE_MODEL_ID}"
BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/judge-system.txt" \
  --arg key "$KEY" \
  --arg name "$LD_JUDGE_NAME" \
  --arg metric "$LD_JUDGE_METRIC" \
  --arg mid "$LD_JUDGE_MODEL_ID" \
  '{
    key: $key,
    name: $name,
    description: "Sonnet judge for a generated LaunchDarkly Terraform file. Score the brief. Validate is context.",
    mode: "judge",
    tags: ["lunch-marcoly", "model-demos", "terraform-codegen", "judge"],
    evaluationMetricKey: $metric,
    isInverted: false,
    defaultVariation: {
      key: "default",
      name: "default",
      model: {
        modelName: $mid,
        parameters: { temperature: 0 }
      },
      messages: [
        { role: "system", content: $sys }
      ]
    }
  }')"

api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs" \
  -H "Content-Type: application/json" \
  -d "$BODY" | jq '{key, name, mode, evaluationMetricKey, variations: [.variations[]? | {key, name}]}'

if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "warning: LD_ENVIRONMENT_KEY unset — skip judge targeting." >&2
  echo "Done. Judge key: ${KEY}"
  exit 0
fi

echo "==> Targeting fallthrough → default (${LD_ENVIRONMENT_KEY})"
TARGETING="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${KEY}/targeting?env=${LD_ENVIRONMENT_KEY}")"
VARIATION_ID="$(echo "$TARGETING" | jq -r '
  .variations[]
  | select((.key // "") == "default" or (.name // "") == "default")
  | ._id
' | head -n1)"
if [[ -z "$VARIATION_ID" || "$VARIATION_ID" == "null" ]]; then
  echo "error: could not resolve the default judge variation" >&2
  exit 1
fi

api_ok PATCH "/projects/${LD_PROJECT_KEY}/ai-configs/${KEY}/targeting?env=${LD_ENVIRONMENT_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg env "$LD_ENVIRONMENT_KEY" \
    --arg id "$VARIATION_ID" \
    '{
      environmentKey: $env,
      comment: "04 terraform codegen judge: fallthrough → default",
      instructions: [
        { kind: "updateFallthroughVariationOrRollout", variationId: $id }
      ]
    }')" | jq --arg env "$LD_ENVIRONMENT_KEY" '
      .environments[$env] // .environments[.environments | keys[0]]
      | {fallthrough}'

echo "Done. Judge key: ${KEY}"
echo "The app calls ${LD_JUDGE_MODEL_ID}. Export ANTHROPIC_API_KEY."
