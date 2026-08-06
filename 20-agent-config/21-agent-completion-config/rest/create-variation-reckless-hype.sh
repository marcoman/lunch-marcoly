#!/usr/bin/env bash
# LaunchDarkly capability: AgentControl — create reckless-hype variation
# Thoughtless Toby voice: no caution, fabricates freely, sweeping claims, defunct-company tips.
# https://launchdarkly.com/docs/api/agent-control/post-ai-config-variation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

CONFIG_KEY="${1:-$LD_CONFIG_KEY}"
VARIATION_KEY="reckless-hype"
MESSAGES_DIR="${SCRIPT_DIR}/messages"

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}")"
if [[ "$STATUS" != "200" ]]; then
  echo "error: AI config ${CONFIG_KEY} not found. Run ./create-config.sh first." >&2
  exit 1
fi

EXISTING="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}")"
if echo "$EXISTING" | jq -e --arg k "$VARIATION_KEY" '.variations[]? | select(.key == $k)' >/dev/null; then
  echo "Variation ${VARIATION_KEY} already exists on ${CONFIG_KEY} — skipping create."
  echo "$EXISTING" | jq --arg k "$VARIATION_KEY" '.variations[] | select(.key == $k) | {key, name, modelConfigKey}'
  exit 0
fi

echo "Creating variation ${VARIATION_KEY} on ${CONFIG_KEY}..."
BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/reckless-system.txt" \
  --rawfile user "${MESSAGES_DIR}/reckless-user.txt" \
  --arg mck "$LD_MODEL_CONFIG_KEY" \
  --arg mid "$LD_MODEL_ID" \
  --arg key "$VARIATION_KEY" \
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

api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/variations" \
  -H "Content-Type: application/json" \
  -d "$BODY" | jq '{key, name, modelConfigKey, model}'

echo "Done. Wire persona targeting with: ./update-name-targeting.sh"
