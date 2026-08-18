#!/usr/bin/env bash
# LaunchDarkly capability: AgentControl — create an AI model config (custom / Ollama)
# Registers a model the completion variations can reference via modelConfigKey.
# https://launchdarkly.com/docs/api/agent-control/post-model-config
# https://launchdarkly.com/docs/home/agentcontrol/create-model-config
#
# Usage:
#   ./create-model-config.sh
#   ./create-model-config.sh <config_key> <model_id> [display_name]
#
# Defaults (no args): best-tier env vars (Custom.llama3.2-3b / llama3.2:3b).
# create-config.sh calls this three times for best / default / simple tiers.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

KEY="${1:-$LD_MODEL_CONFIG_KEY}"
ID="${2:-$LD_MODEL_ID}"
NAME="${3:-${LD_MODEL_DISPLAY_NAME:-Ollama ${ID}}}"
PROVIDER="${LD_MODEL_PROVIDER:-Custom}"

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/model-configs/${KEY}")"
if [[ "$STATUS" == "200" ]]; then
  echo "Model config ${KEY} already exists — skipping create."
  api GET "/projects/${LD_PROJECT_KEY}/ai-configs/model-configs/${KEY}" \
    | jq '{key, name, id, provider, version}'
  exit 0
fi

echo "Creating model config ${KEY} (id=${ID}, provider=${PROVIDER})..."
api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/model-configs" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg name "$NAME" \
    --arg key "$KEY" \
    --arg id "$ID" \
    --arg provider "$PROVIDER" \
    '{
      name: $name,
      key: $key,
      id: $id,
      provider: $provider,
      tags: ["lunch-marcoly", "ollama", "agent-completion"]
    }')" | jq '{key, name, id, provider, version}'

echo "Done."
