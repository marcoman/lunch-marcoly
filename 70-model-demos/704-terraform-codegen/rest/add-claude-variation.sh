#!/usr/bin/env bash
# Add claude-sonnet to an existing terraform-codegen-compare config, then retarget.
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

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}")"
if [[ "$STATUS" != "200" ]]; then
  echo "error: AI config ${LD_CONFIG_KEY} was not found (HTTP ${STATUS})." >&2
  echo "Create it first: ./create-config.sh" >&2
  exit 1
fi

CONFIG="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}")"
HAS="$(echo "$CONFIG" | jq -r --arg key "$LD_ANTHROPIC_VARIATION_KEY" '
  [.variations[]? | select((.key // "") == $key or (.name // "") == $key)] | length
')"

if [[ "$HAS" == "0" ]]; then
  echo "==> Variation ${LD_ANTHROPIC_VARIATION_KEY} → ${LD_ANTHROPIC_MODEL_ID}"
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
else
  echo "Variation ${LD_ANTHROPIC_VARIATION_KEY} already exists — skipping create."
fi

echo "==> Targeting"
"${SCRIPT_DIR}/update-targeting.sh"
echo "Done. Export ANTHROPIC_API_KEY, restart the app, and check ${LD_ANTHROPIC_VARIATION_KEY}."
