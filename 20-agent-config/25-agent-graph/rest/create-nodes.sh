#!/usr/bin/env bash
# Create the six agent-mode node configs for equity-briefing-graph.
# LaunchDarkly: Agents (mode=agent) · instructions · modelConfigKey
# https://launchdarkly.com/docs/api/agent-control/post-ai-config
# https://launchdarkly.com/docs/home/agentcontrol/agents

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"

echo "==> Model configs"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_CONFIG_KEY" "$LD_MODEL_ID" "$LD_MODEL_DISPLAY_NAME"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_SIMPLE_CONFIG_KEY" "$LD_MODEL_SIMPLE_ID" "$LD_MODEL_SIMPLE_DISPLAY_NAME"

create_agent_node() {
  local key="$1"
  local name="$2"
  local instructions_file="$3"
  local model_config_key="${4:-$LD_MODEL_CONFIG_KEY}"
  local model_id="${5:-$LD_MODEL_ID}"

  local status
  status="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${key}")"
  if [[ "$status" == "200" ]]; then
    echo "skip: ${key} already exists"
    return 0
  fi

  echo "==> Agent config ${key}"
  local body
  body="$(jq -n \
    --rawfile instructions "${MESSAGES_DIR}/${instructions_file}" \
    --arg key "$key" \
    --arg name "$name" \
    --arg mck "$model_config_key" \
    --arg mid "$model_id" \
    '{
      key: $key,
      name: $name,
      description: ("Graph node for " + $key),
      mode: "agent",
      tags: ["lunch-marcoly", "agent-graph", "equity-briefing"],
      defaultVariation: {
        key: "default",
        name: "default",
        modelConfigKey: $mck,
        model: { modelName: $mid },
        instructions: ($instructions | gsub("\\n$"; ""))
      }
    }')"

  api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs" \
    -H "Content-Type: application/json" \
    -d "$body" | jq '{key, name, mode, variations: [.variations[]? | {key, name, modelConfigKey}]}'
}

create_agent_node "$LD_NODE_ASSESS" "Graph assess" "assess-instructions.txt"
create_agent_node "$LD_NODE_QUESTIONS" "Graph questions" "questions-instructions.txt"
create_agent_node "$LD_NODE_GOOD" "Graph good & bad" "good-instructions.txt"
create_agent_node "$LD_NODE_JOKE" "Graph joke" "joke-instructions.txt"
create_agent_node "$LD_NODE_FINALIZE" "Graph finalize" "finalize-instructions.txt"

# Report node: default = baseline (Amelia fallthrough); add Charlie + Toby variations.
REPORT_STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_NODE_REPORT}")"
if [[ "$REPORT_STATUS" == "200" ]]; then
  echo "skip: ${LD_NODE_REPORT} already exists"
else
  echo "==> Agent config ${LD_NODE_REPORT} (default=baseline-analyst)"
  REPORT_BODY="$(jq -n \
    --rawfile instructions "${MESSAGES_DIR}/report-baseline-instructions.txt" \
    --arg key "$LD_NODE_REPORT" \
    --arg name "Graph report" \
    --arg mck "$LD_MODEL_CONFIG_KEY" \
    --arg mid "$LD_MODEL_ID" \
    '{
      key: $key,
      name: $name,
      description: "Report specialist — persona targeting on this node only",
      mode: "agent",
      tags: ["lunch-marcoly", "agent-graph", "equity-briefing"],
      defaultVariation: {
        key: "baseline-analyst",
        name: "baseline-analyst",
        modelConfigKey: $mck,
        model: { modelName: $mid },
        instructions: ($instructions | gsub("\\n$"; ""))
      }
    }')"
  api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs" \
    -H "Content-Type: application/json" \
    -d "$REPORT_BODY" | jq '{key, name, mode, variations: [.variations[]? | {key, name}]}'

  echo "==> Variation concise-skeptic (Charlie)"
  api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_NODE_REPORT}/variations" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --rawfile instructions "${MESSAGES_DIR}/report-skeptic-instructions.txt" \
      --arg mck "$LD_MODEL_CONFIG_KEY" \
      --arg mid "$LD_MODEL_ID" \
      '{
        key: "concise-skeptic",
        name: "concise-skeptic",
        modelConfigKey: $mck,
        model: { modelName: $mid },
        instructions: ($instructions | gsub("\\n$"; ""))
      }')" | jq '{key, name, modelConfigKey}'

  echo "==> Variation reckless-hype (Toby)"
  api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_NODE_REPORT}/variations" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --rawfile instructions "${MESSAGES_DIR}/report-reckless-instructions.txt" \
      --arg mck "$LD_MODEL_SIMPLE_CONFIG_KEY" \
      --arg mid "$LD_MODEL_SIMPLE_ID" \
      '{
        key: "reckless-hype",
        name: "reckless-hype",
        modelConfigKey: $mck,
        model: { modelName: $mid },
        instructions: ($instructions | gsub("\\n$"; ""))
      }')" | jq '{key, name, modelConfigKey}'
fi

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "==> Report name targeting"
  "${SCRIPT_DIR}/update-report-targeting.sh"
else
  echo "warning: LD_ENVIRONMENT_KEY unset — skip report targeting." >&2
  echo "  Run: export LD_ENVIRONMENT_KEY=test && ./update-report-targeting.sh" >&2
fi

echo "Done. Nodes: assess / report / questions / good / joke / finalize"
echo "Next: ./create-graph.sh"
