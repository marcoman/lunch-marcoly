#!/usr/bin/env bash
# Get one graph node AI config (and optional targeting).
# Usage: ./get-config.sh <config-key>
# https://launchdarkly.com/docs/api/agent-control/get-ai-config

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

if [[ $# -lt 1 || -z "${1:-}" ]]; then
  echo "usage: $0 <config-key>" >&2
  echo "  e.g. $0 equity-briefing-graph-report" >&2
  exit 1
fi

CONFIG_KEY="$1"

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
    instructions: (.instructions // "" | if length > 100 then .[0:100] + "…" else . end)
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
