#!/usr/bin/env bash
# LaunchDarkly capability: AgentControl — get AI config
# Retrieves a completion/agent config and summarizes variations + optional targeting.
# https://launchdarkly.com/docs/api/agent-control/get-ai-config
# https://launchdarkly.com/docs/api/agent-control/get-ai-config-targeting

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

CONFIG_KEY="${1:-$LD_CONFIG_KEY}"

echo "Config ${CONFIG_KEY}:"
api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}" | jq '{
  key,
  name,
  mode,
  description,
  tags,
  variations: [.variations[]? | {
    key,
    name,
    modelConfigKey,
    modelName: .model.modelName,
    tools,
    messages: [.messages[]? | {
      role,
      content: (.content | if length > 80 then .[0:80] + "…" else . end)
    }]
  }]
}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo
  echo "Targeting (${LD_ENVIRONMENT_KEY}):"
  api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/targeting?env=${LD_ENVIRONMENT_KEY}" | jq --arg env "$LD_ENVIRONMENT_KEY" '{
    variations: [.variations[] | {key, name, _id}],
    environment: (.environments[$env] // null | {on, fallthrough, offVariation})
  }'
fi
