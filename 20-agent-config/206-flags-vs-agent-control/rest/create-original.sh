#!/usr/bin/env bash
# LaunchDarkly: AgentControl — Original variation for 26-flags-vs-agent-control
# Creates:
#   equity-briefing-flag-compare          completion (Charlie rule, Toby fallthrough)
#   equity-briefing-flag-compare-judge    one judge, score only
# https://launchdarkly.com/docs/home/agentcontrol/quickstart
# https://launchdarkly.com/docs/home/agentcontrol/judges

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"

echo "==> Model configs (Charlie best, Toby simple, judge best)"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_BEST_CONFIG_KEY" "$LD_MODEL_BEST_ID" "$LD_MODEL_BEST_DISPLAY_NAME"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_SIMPLE_CONFIG_KEY" "$LD_MODEL_SIMPLE_ID" "$LD_MODEL_SIMPLE_DISPLAY_NAME"

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}")"
if [[ "$STATUS" == "200" ]]; then
  echo "AI config ${LD_CONFIG_KEY} already exists — leaving it."
else
  echo "==> AI config ${LD_CONFIG_KEY} (defaultVariation=reckless-hype → ${LD_MODEL_SIMPLE_ID})"
  CREATE_BODY="$(jq -n \
    --rawfile sys "${MESSAGES_DIR}/reckless-system.txt" \
    --rawfile user "${MESSAGES_DIR}/reckless-user.txt" \
    --arg key "$LD_CONFIG_KEY" \
    --arg name "$LD_CONFIG_NAME" \
    --arg mck "$LD_MODEL_SIMPLE_CONFIG_KEY" \
    --arg mid "$LD_MODEL_SIMPLE_ID" \
    '{
      key: $key,
      name: $name,
      description: "26 Original source. Toby fallthrough is reckless-hype. Charlie is a name rule to concise-skeptic.",
      mode: "completion",
      tags: ["lunch-marcoly", "26-flags-vs-agent-control", "original"],
      defaultVariation: {
        key: "reckless-hype",
        name: "reckless-hype",
        modelConfigKey: $mck,
        model: { modelName: $mid },
        messages: [
          { role: "system", content: $sys },
          { role: "user", content: $user }
        ]
      }
    }')"
  api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs" \
    -H "Content-Type: application/json" \
    -d "$CREATE_BODY" | jq '{key, name, mode}'

  echo "==> Variation concise-skeptic → ${LD_MODEL_BEST_ID}"
  SKEPTIC_BODY="$(jq -n \
    --rawfile sys "${MESSAGES_DIR}/skeptic-system.txt" \
    --rawfile user "${MESSAGES_DIR}/skeptic-user.txt" \
    --arg mck "$LD_MODEL_BEST_CONFIG_KEY" \
    --arg mid "$LD_MODEL_BEST_ID" \
    '{
      key: "concise-skeptic",
      name: "concise-skeptic",
      modelConfigKey: $mck,
      model: { modelName: $mid },
      messages: [
        { role: "system", content: $sys },
        { role: "user", content: $user }
      ]
    }')"
  api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/variations" \
    -H "Content-Type: application/json" \
    -d "$SKEPTIC_BODY" | jq '{key, name, modelConfigKey}'
fi

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "==> Name rule + fallthrough"
  "${SCRIPT_DIR}/update-name-targeting.sh" "$LD_CONFIG_KEY"
else
  echo "warning: LD_ENVIRONMENT_KEY unset — skip targeting." >&2
fi

JUDGE_STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_JUDGE_KEY}")"
if [[ "$JUDGE_STATUS" == "200" ]]; then
  echo "Judge ${LD_JUDGE_KEY} already exists — leaving it."
else
  echo "==> Judge ${LD_JUDGE_KEY}"
  JUDGE_BODY="$(jq -n \
    --rawfile sys "${MESSAGES_DIR}/judge-system.txt" \
    --arg key "$LD_JUDGE_KEY" \
    --arg name "$LD_JUDGE_NAME" \
    --arg metric "$LD_JUDGE_METRIC" \
    --arg mck "$LD_MODEL_BEST_CONFIG_KEY" \
    --arg mid "$LD_MODEL_BEST_ID" \
    '{
      key: $key,
      name: $name,
      description: "26 Original source. Scores the draft. Does not rewrite it.",
      mode: "judge",
      tags: ["lunch-marcoly", "26-flags-vs-agent-control", "original"],
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
  api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs" \
    -H "Content-Type: application/json" \
    -d "$JUDGE_BODY" | jq '{key, name, mode, evaluationMetricKey}'
  if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
    LD_CONFIG_KEY="$LD_JUDGE_KEY" "${SCRIPT_DIR}/update-targeting.sh" default "$LD_JUDGE_KEY"
  fi
fi

echo "Done."
echo "  completion: ${LD_CONFIG_KEY}"
echo "  judge:      ${LD_JUDGE_KEY}"
echo "Pull: ollama pull ${LD_MODEL_BEST_ID} && ollama pull ${LD_MODEL_SIMPLE_ID}"
