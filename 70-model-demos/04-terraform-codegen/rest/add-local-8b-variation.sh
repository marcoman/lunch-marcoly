#!/usr/bin/env bash
# Add local-8b (llama3.1:8b) to an existing terraform-codegen-compare config, then retarget.
# LaunchDarkly: POST AI config variation
# https://launchdarkly.com/docs/api/agent-control/post-ai-config-variation
# https://launchdarkly.com/docs/home/agentcontrol/target

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

MESSAGES_DIR="${SCRIPT_DIR}/messages"

echo "==> Model config ${LD_MODEL_CEILING_CONFIG_KEY}"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_CEILING_CONFIG_KEY" "$LD_MODEL_CEILING_ID" "$LD_MODEL_CEILING_DISPLAY_NAME"

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}")"
if [[ "$STATUS" != "200" ]]; then
  echo "error: AI config ${LD_CONFIG_KEY} was not found (HTTP ${STATUS})." >&2
  echo "Create it first: ./create-config.sh" >&2
  exit 1
fi

CONFIG="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}")"
HAS="$(echo "$CONFIG" | jq -r --arg key "$LD_MODEL_CEILING_VARIATION_KEY" '
  [.variations[]? | select((.key // "") == $key or (.name // "") == $key)] | length
')"

if [[ "$HAS" == "0" ]]; then
  echo "==> Variation ${LD_MODEL_CEILING_VARIATION_KEY} → ${LD_MODEL_CEILING_ID}"
  BODY="$(jq -n \
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
    -d "$BODY" | jq '{key, name, modelConfigKey, model}'
else
  echo "Variation ${LD_MODEL_CEILING_VARIATION_KEY} already exists — skipping create."
fi

echo "==> Targeting"
"${SCRIPT_DIR}/update-targeting.sh"
echo "Done. Pull the model when ready: ollama pull ${LD_MODEL_CEILING_ID}"
