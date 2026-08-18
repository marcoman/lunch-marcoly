#!/usr/bin/env bash
# LaunchDarkly: AgentControl — create equity-briefing-judged (completion)
# Variations:
#   concise-skeptic (Charlie / rewrite) → llama3.2:3b
#   reckless-hype   (Toby / draft)      → llama3.2:1b
# Fallthrough → concise-skeptic (safe default).
# https://launchdarkly.com/docs/api/agent-control/post-ai-config

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"

echo "==> Model configs"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_BEST_CONFIG_KEY" "$LD_MODEL_BEST_ID" "$LD_MODEL_BEST_DISPLAY_NAME"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_SIMPLE_CONFIG_KEY" "$LD_MODEL_SIMPLE_ID" "$LD_MODEL_SIMPLE_DISPLAY_NAME"

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}")"
if [[ "$STATUS" == "200" ]]; then
  echo "error: AI config ${LD_CONFIG_KEY} already exists." >&2
  echo "Delete it first: ./delete-config.sh ${LD_CONFIG_KEY}" >&2
  exit 1
fi

echo "==> AI config ${LD_CONFIG_KEY} (defaultVariation=concise-skeptic → ${LD_MODEL_BEST_ID})"
CREATE_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/skeptic-system.txt" \
  --rawfile user "${MESSAGES_DIR}/skeptic-user.txt" \
  --arg key "$LD_CONFIG_KEY" \
  --arg name "$LD_CONFIG_NAME" \
  --arg mck "$LD_MODEL_BEST_CONFIG_KEY" \
  --arg mid "$LD_MODEL_BEST_ID" \
  '{
    key: $key,
    name: $name,
    description: "Judged equity briefing: Toby reckless draft + Charlie skeptic rewrite after custom judges fail.",
    mode: "completion",
    tags: ["lunch-marcoly", "agent-judges", "equity-briefing"],
    defaultVariation: {
      key: "concise-skeptic",
      name: "concise-skeptic",
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

echo "==> Variation reckless-hype → ${LD_MODEL_SIMPLE_ID}"
RECKLESS_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/reckless-system.txt" \
  --rawfile user "${MESSAGES_DIR}/reckless-user.txt" \
  --arg mck "$LD_MODEL_SIMPLE_CONFIG_KEY" \
  --arg mid "$LD_MODEL_SIMPLE_ID" \
  '{
    key: "reckless-hype",
    name: "reckless-hype",
    modelConfigKey: $mck,
    model: { modelName: $mid },
    messages: [
      { role: "system", content: $sys },
      { role: "user", content: $user }
    ]
  }')"

api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/variations" \
  -H "Content-Type: application/json" \
  -d "$RECKLESS_BODY" | jq '{key, name, modelConfigKey, model}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "==> Targeting fallthrough → concise-skeptic (${LD_ENVIRONMENT_KEY})"
  "${SCRIPT_DIR}/update-targeting.sh" concise-skeptic
  echo "==> Name rules: Charlie → skeptic, Toby → reckless"
  "${SCRIPT_DIR}/update-name-targeting.sh"
else
  echo "warning: LD_ENVIRONMENT_KEY unset — skip targeting." >&2
  echo "  Run: export LD_ENVIRONMENT_KEY=test && ./update-targeting.sh concise-skeptic && ./update-name-targeting.sh" >&2
fi

echo "Done. Config key: ${LD_CONFIG_KEY}"
echo "Create judges first (or next): ./create-judges.sh"
echo "Pull: ollama pull ${LD_MODEL_BEST_ID} && ollama pull ${LD_MODEL_SIMPLE_ID}"
echo "UI: ${LD_API_HOST}/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}"
