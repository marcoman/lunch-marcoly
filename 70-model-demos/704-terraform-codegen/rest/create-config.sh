#!/usr/bin/env bash
# LaunchDarkly: AgentControl — one completion config, three variations
#   local-3b → llama3.2:3b (fallthrough, unchecked on the screen)
#   local-1b → llama3.2:1b (user key codegen-1b)
#   local-8b → llama3.1:8b (user key codegen-8b)
#   claude-haiku → claude-haiku-4-5 (user key codegen-haiku)
#   claude-sonnet → claude-sonnet-5 (user key codegen-sonnet)
# Same messages. The app evaluates each selected context on one click.
# https://launchdarkly.com/docs/api/agent-control/post-ai-config
# https://launchdarkly.com/docs/api/agent-control/post-ai-config-variation
# https://launchdarkly.com/docs/home/agentcontrol/quickstart

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"

echo "==> Model configs"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_LARGE_CONFIG_KEY" "$LD_MODEL_LARGE_ID" "$LD_MODEL_LARGE_DISPLAY_NAME"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_CEILING_CONFIG_KEY" "$LD_MODEL_CEILING_ID" "$LD_MODEL_CEILING_DISPLAY_NAME"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_SMALL_CONFIG_KEY" "$LD_MODEL_SMALL_ID" "$LD_MODEL_SMALL_DISPLAY_NAME"

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}")"
if [[ "$STATUS" == "200" ]]; then
  echo "error: AI config ${LD_CONFIG_KEY} already exists." >&2
  echo "Delete it first: ./delete-config.sh" >&2
  exit 1
fi

echo "==> AI config ${LD_CONFIG_KEY} (mode=completion, defaultVariation=local-3b)"
CREATE_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/system.txt" \
  --rawfile user "${MESSAGES_DIR}/user.txt" \
  --arg key "$LD_CONFIG_KEY" \
  --arg name "$LD_CONFIG_NAME" \
  --arg mck "$LD_MODEL_LARGE_CONFIG_KEY" \
  --arg mid "$LD_MODEL_LARGE_ID" \
  '{
    key: $key,
    name: $name,
    description: "Compare models writing the same LaunchDarkly Terraform file. Descriptions come from the resource name. The ancestry comment is the intended diff.",
    mode: "completion",
    tags: ["lunch-marcoly", "model-demos", "terraform-codegen"],
    defaultVariation: {
      key: "local-3b",
      name: "local-3b",
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
  -d "$CREATE_BODY" | jq '{key, name, mode, variations: [.variations[]? | {key, name, modelConfigKey}]}'

echo "==> Variation local-1b → ${LD_MODEL_SMALL_ID}"
SMALL_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/system.txt" \
  --rawfile user "${MESSAGES_DIR}/user.txt" \
  --arg mck "$LD_MODEL_SMALL_CONFIG_KEY" \
  --arg mid "$LD_MODEL_SMALL_ID" \
  '{
    key: "local-1b",
    name: "local-1b",
    modelConfigKey: $mck,
    model: { modelName: $mid },
    messages: [
      { role: "system", content: $sys },
      { role: "user", content: $user }
    ]
  }')"

api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/variations" \
  -H "Content-Type: application/json" \
  -d "$SMALL_BODY" | jq '{key, name, modelConfigKey, model}'

echo "==> Variation ${LD_MODEL_CEILING_VARIATION_KEY} → ${LD_MODEL_CEILING_ID}"
CEILING_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/system.txt" \
  --rawfile user "${MESSAGES_DIR}/user.txt" \
  --arg key "$LD_MODEL_CEILING_VARIATION_KEY" \
  --arg mck "$LD_MODEL_CEILING_CONFIG_KEY" \
  --arg mid "$LD_MODEL_CEILING_ID" \
  '{
    key: $key,
    name: $key,
    modelConfigKey: $mck,
    model: { modelName: $mid },
    messages: [
      { role: "system", content: $sys },
      { role: "user", content: $user }
    ]
  }')"

api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/variations" \
  -H "Content-Type: application/json" \
  -d "$CEILING_BODY" | jq '{key, name, modelConfigKey, model}'

echo "==> Variation ${LD_HAIKU_VARIATION_KEY} → ${LD_HAIKU_MODEL_ID}"
HAIKU_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/system.txt" \
  --rawfile user "${MESSAGES_DIR}/user.txt" \
  --arg key "$LD_HAIKU_VARIATION_KEY" \
  --arg mid "$LD_HAIKU_MODEL_ID" \
  '{
    key: $key,
    name: $key,
    model: { modelName: $mid },
    messages: [
      { role: "system", content: $sys },
      { role: "user", content: $user }
    ]
  }')"

api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/variations" \
  -H "Content-Type: application/json" \
  -d "$HAIKU_BODY" | jq '{key, name, modelConfigKey, model}'

echo "==> Variation ${LD_ANTHROPIC_VARIATION_KEY} → ${LD_ANTHROPIC_MODEL_ID}"
# Provider Anthropic is inferred by the app from the claude-* model id.
ANTHROPIC_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/system.txt" \
  --rawfile user "${MESSAGES_DIR}/user.txt" \
  --arg key "$LD_ANTHROPIC_VARIATION_KEY" \
  --arg mid "$LD_ANTHROPIC_MODEL_ID" \
  '{
    key: $key,
    name: $key,
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
  echo "==> Targeting: codegen-1b → local-1b, codegen-8b → ${LD_MODEL_CEILING_VARIATION_KEY}, codegen-sonnet → ${LD_ANTHROPIC_VARIATION_KEY}, fallthrough → local-3b"
  "${SCRIPT_DIR}/update-targeting.sh"
else
  echo "warning: LD_ENVIRONMENT_KEY unset — skip targeting." >&2
  echo "  Run: export LD_ENVIRONMENT_KEY=test && ./update-targeting.sh" >&2
fi

echo "Done. Config key: ${LD_CONFIG_KEY}"
echo "Pull locally when ready:"
echo "  ollama pull ${LD_MODEL_SMALL_ID}"
echo "  ollama pull ${LD_MODEL_CEILING_ID}"
echo "  ollama pull ${LD_MODEL_LARGE_ID}"
echo "Claude: export ANTHROPIC_API_KEY=… then check ${LD_ANTHROPIC_VARIATION_KEY}"
