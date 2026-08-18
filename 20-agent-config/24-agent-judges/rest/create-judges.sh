#!/usr/bin/env bash
# LaunchDarkly: AgentControl — create custom Judges (mode=judge)
# Creates:
#   equity-briefing-source-fidelity
#   equity-briefing-recommendation-discipline
# Both use Ollama llama3.2:3b (Custom.llama3.2-3b).
# https://launchdarkly.com/docs/home/agentcontrol/judges
# https://launchdarkly.com/docs/api/agent-control/post-ai-config

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"

echo "==> Model config for judges → ${LD_MODEL_BEST_ID}"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_BEST_CONFIG_KEY" "$LD_MODEL_BEST_ID" "$LD_MODEL_BEST_DISPLAY_NAME"

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

  echo "==> Judge ${key} (metric=${metric}, model=${LD_MODEL_BEST_ID})"
  local body created
  body="$(jq -n \
    --rawfile sys "${MESSAGES_DIR}/${sys_file}" \
    --arg key "$key" \
    --arg name "$name" \
    --arg metric "$metric" \
    --arg mck "$LD_MODEL_BEST_CONFIG_KEY" \
    --arg mid "$LD_MODEL_BEST_ID" \
    '{
      key: $key,
      name: $name,
      description: ("Custom judge for 24-agent-judges: " + $name),
      mode: "judge",
      tags: ["lunch-marcoly", "agent-judges", "equity-briefing"],
      evaluationMetricKey: $metric,
      isInverted: false,
      defaultVariation: {
        key: "default",
        name: "default",
        modelConfigKey: $mck,
        model: { modelName: $mid },
        messages: [
          { role: "system", content: $sys }
        ]
      }
    }')"

  # Capture body first so a failed create does not pipe empty JSON into jq
  # (which previously printed a confusing {key: null, ...} object).
  created="$(api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs" \
    -H "Content-Type: application/json" \
    -d "$body")"
  echo "$created" | jq '{key, name, mode, evaluationMetricKey, isInverted, variations: [.variations[]? | {key, name, modelConfigKey}]}'

  # Enable fallthrough on the default variation when environment is set.
  if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
    echo "==> Targeting fallthrough → default (${key} / ${LD_ENVIRONMENT_KEY})"
    LD_CONFIG_KEY="$key" "${SCRIPT_DIR}/update-targeting.sh" default "$key"
  else
    echo "warning: LD_ENVIRONMENT_KEY unset — skip judge targeting for ${key}." >&2
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
echo "Pull locally: ollama pull ${LD_MODEL_BEST_ID}"
