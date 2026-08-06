#!/usr/bin/env bash
# LaunchDarkly capability: AgentControl — create an AI model config (custom / Ollama)
# Registers a model the completion variations can reference via modelConfigKey.
# https://launchdarkly.com/docs/api/agent-control/post-model-config
# https://launchdarkly.com/docs/home/agentcontrol/create-model-config

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/model-configs/${LD_MODEL_CONFIG_KEY}")"
if [[ "$STATUS" == "200" ]]; then
  echo "Model config ${LD_MODEL_CONFIG_KEY} already exists — skipping create."
  api GET "/projects/${LD_PROJECT_KEY}/ai-configs/model-configs/${LD_MODEL_CONFIG_KEY}" \
    | jq '{key, name, id, provider, version}'
  exit 0
fi

echo "Creating model config ${LD_MODEL_CONFIG_KEY} (id=${LD_MODEL_ID}, provider=${LD_MODEL_PROVIDER})..."
api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/model-configs" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg name "$LD_MODEL_DISPLAY_NAME" \
    --arg key "$LD_MODEL_CONFIG_KEY" \
    --arg id "$LD_MODEL_ID" \
    --arg provider "$LD_MODEL_PROVIDER" \
    '{
      name: $name,
      key: $key,
      id: $id,
      provider: $provider,
      tags: ["lunch-marcoly", "ollama", "agent-completion"]
    }')" | jq '{key, name, id, provider, version}'

echo "Done."
