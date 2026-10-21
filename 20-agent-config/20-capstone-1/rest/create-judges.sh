#!/usr/bin/env bash
# LaunchDarkly: AgentControl — create the two capstone judges (mode=judge).
# Both use Ollama llama3.2:3b. Scores do not rewrite the draft.
# https://launchdarkly.com/docs/home/agentcontrol/judges
# https://launchdarkly.com/docs/api/agent-control/post-ai-config

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"

echo "==> Model config for judges → ${LD_MODEL_ID}"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_CONFIG_KEY" "$LD_MODEL_ID" "$LD_MODEL_DISPLAY_NAME"

create_judge() {
  local key="$1"
  local name="$2"
  local metric="$3"
  local sys_file="$4"

  local status
  status="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${key}")"
  if [[ "$status" == "200" ]]; then
    echo "Judge ${key} already exists — skipping create."
    api GET "/projects/${LD_PROJECT_KEY}/ai-configs/${key}" \
      | jq '{key, name, mode, evaluationMetricKey, isInverted}'
    return 0
  fi

  echo "==> Judge ${key} (metric=${metric}, model=${LD_MODEL_ID})"
  local body created
  body="$(jq -n \
    --rawfile sys "${MESSAGES_DIR}/${sys_file}" \
    --arg key "$key" \
    --arg name "$name" \
    --arg metric "$metric" \
    --arg mck "$LD_MODEL_CONFIG_KEY" \
    --arg mid "$LD_MODEL_ID" \
    '{
      key: $key,
      name: $name,
      description: ("Custom judge for 20-capstone-1: " + $name),
      mode: "judge",
      tags: ["lunch-marcoly", "capstone", "equity-briefing"],
      evaluationMetricKey: $metric,
      isInverted: false,
      defaultVariation: {
        key: "default",
        name: "default",
        modelConfigKey: $mck,
        model: {
          modelName: $mid,
          parameters: { temperature: 0 }
        },
        messages: [
          { role: "system", content: $sys }
        ]
      }
    }')"

  created="$(api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs" \
    -H "Content-Type: application/json" \
    -d "$body")"
  echo "$created" | jq '{key, name, mode, evaluationMetricKey, isInverted, variations: [.variations[]? | {key, name, modelConfigKey}]}'

  # A new config falls through to the disabled variation until the environment
  # default rule points at the real variation.
  if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
    local targeting variation_id
    targeting="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${key}/targeting?env=${LD_ENVIRONMENT_KEY}")"
    variation_id="$(echo "$targeting" | jq -r '
      .variations[]
      | select(
          (.key // "") == "default"
          or (.name // "") == "default"
          or (.value._ldMeta.variationKey // "") == "default"
        )
      | ._id
    ' | head -n1)"
    if [[ -z "$variation_id" || "$variation_id" == "null" ]]; then
      echo "error: ${key} has no default variation to serve" >&2
      exit 1
    fi
    echo "==> Fallthrough → default (${key} / ${LD_ENVIRONMENT_KEY})"
    api_ok PATCH "/projects/${LD_PROJECT_KEY}/ai-configs/${key}/targeting?env=${LD_ENVIRONMENT_KEY}" \
      -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
      -d "$(jq -n \
        --arg env "$LD_ENVIRONMENT_KEY" \
        --arg vid "$variation_id" \
        '{
          environmentKey: $env,
          comment: "Judge fallthrough serves the default variation",
          instructions: [{ kind: "updateFallthroughVariationOrRollout", variationId: $vid }]
        }')" | jq --arg env "$LD_ENVIRONMENT_KEY" '
          .environments[$env] // .environments[.environments | keys[0]]
          | {on, fallthrough, offVariation}
        '
  fi
}

create_judge \
  "$LD_JUDGE_FIDELITY_KEY" \
  "$LD_JUDGE_FIDELITY_NAME" \
  "$LD_JUDGE_FIDELITY_METRIC" \
  "judge-source-fidelity-system.txt"

create_judge \
  "$LD_JUDGE_DISCIPLINE_KEY" \
  "$LD_JUDGE_DISCIPLINE_NAME" \
  "$LD_JUDGE_DISCIPLINE_METRIC" \
  "judge-recommendation-discipline-system.txt"

echo "Done. Judges:"
echo "  ${LD_JUDGE_FIDELITY_KEY}  (metric ${LD_JUDGE_FIDELITY_METRIC})"
echo "  ${LD_JUDGE_DISCIPLINE_KEY}  (metric ${LD_JUDGE_DISCIPLINE_METRIC})"
echo "Pull locally: ollama pull ${LD_MODEL_ID}"
