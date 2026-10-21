#!/usr/bin/env bash
# LaunchDarkly: create equity-briefing-tracked-completion (completion mode)
# Variations:
#   tracked-ollama     → llama3.2:1b (fallthrough / Anonymous Amelia)
#   tracked-anthropic  → claude-sonnet-5 (Best Betty)
# https://launchdarkly.com/docs/api/agent-control/post-ai-config
# https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"

echo "==> Model config (Ollama default)"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_OLLAMA_CONFIG_KEY" "$LD_MODEL_OLLAMA_ID" "$LD_MODEL_OLLAMA_DISPLAY_NAME"

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}")"
if [[ "$STATUS" == "200" ]]; then
  echo "error: AI config ${LD_CONFIG_KEY} already exists." >&2
  echo "Delete it first: ./delete-config.sh ${LD_CONFIG_KEY}" >&2
  exit 1
fi

echo "==> AI config ${LD_CONFIG_KEY} (defaultVariation=tracked-ollama → ${LD_MODEL_OLLAMA_ID})"
CREATE_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/tracked-ollama-system.txt" \
  --rawfile user "${MESSAGES_DIR}/tracked-ollama-user.txt" \
  --arg key "$LD_CONFIG_KEY" \
  --arg name "$LD_CONFIG_NAME" \
  --arg mck "$LD_MODEL_OLLAMA_CONFIG_KEY" \
  --arg mid "$LD_MODEL_OLLAMA_ID" \
  '{
    key: $key,
    name: $name,
    description: "Tracked completion config for 22-config-outside-code: Ollama default + Anthropic for Best Betty. Metrics via track_metrics_of + thumbs feedback.",
    mode: "completion",
    tags: ["lunch-marcoly", "agent-completion", "equity-briefing", "tracked"],
    defaultVariation: {
      key: "tracked-ollama",
      name: "tracked-ollama",
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
  -d "$CREATE_BODY" | jq '{key, name, mode, tags, variations: [.variations[]? | {key, name, modelConfigKey}]}'

echo "==> Variation tracked-anthropic → ${LD_ANTHROPIC_MODEL_ID} (Best Betty)"
# Provider Anthropic is inferred by the app from claude-* model ids.
ANTHROPIC_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/tracked-anthropic-system.txt" \
  --rawfile user "${MESSAGES_DIR}/tracked-anthropic-user.txt" \
  --arg mid "$LD_ANTHROPIC_MODEL_ID" \
  '{
    key: "tracked-anthropic",
    name: "tracked-anthropic",
    model: { modelName: $mid },
    messages: [
      { role: "system", content: $sys },
      { role: "user", content: $user }
    ]
  }')"

api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/variations" \
  -H "Content-Type: application/json" \
  -d "$ANTHROPIC_BODY" | jq '{key, name, modelConfigKey, model}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "==> Targeting fallthrough → tracked-ollama (${LD_ENVIRONMENT_KEY})"
  "${SCRIPT_DIR}/update-targeting.sh" tracked-ollama
  echo "==> Name rule for Best Betty: ./update-name-targeting.sh"
fi

echo
echo "Created ${LD_CONFIG_KEY}."
echo "UI: ${LD_API_HOST}/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}"
echo "Pull Ollama: ollama pull ${LD_MODEL_OLLAMA_ID}"
echo "Anthropic: export ANTHROPIC_API_KEY=… (Best Betty)"
