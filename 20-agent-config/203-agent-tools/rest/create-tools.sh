#!/usr/bin/env bash
# LaunchDarkly: create Library tools for 23-agent-tools
# https://launchdarkly.com/docs/api/agent-control/post-ai-tool
# https://launchdarkly.com/docs/home/agentcontrol/tools

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

SCHEMAS_DIR="${SCRIPT_DIR}/schemas"

create_tool() {
  local key="$1"
  local description="$2"
  local schema_file="$3"

  local status
  status="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-tools/${key}")"
  if [[ "$status" == "200" ]]; then
    echo "Tool ${key} already exists — skipping create."
    api GET "/projects/${LD_PROJECT_KEY}/ai-tools/${key}" \
      | jq '{key, description, version}'
    return 0
  fi

  echo "==> Creating tool ${key}"
  api_ok POST "/projects/${LD_PROJECT_KEY}/ai-tools" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg key "$key" \
      --arg description "$description" \
      --slurpfile schema "$schema_file" \
      '{
        key: $key,
        description: $description,
        schema: $schema[0],
        tags: ["lunch-marcoly", "agent-tools", "equity-briefing"]
      }')" | jq '{key, description, version}'
}

create_tool \
  "$LD_TOOL_ANALYZE_KEY" \
  "Analyze news headlines for a single ticker. Return claims grounded only in those stories (cite evidence titles)." \
  "${SCHEMAS_DIR}/analyze-ticker-stories.json"

create_tool \
  "$LD_TOOL_COMPARE_KEY" \
  "Compare two ticker analyses. Call ONLY after both analyze-ticker-stories results return. Pass those exact JSON objects as analysis_a and analysis_b (do not invent). Optionally pick a preferred ticker citing evidence titles only." \
  "${SCHEMAS_DIR}/compare-ticker-analyses.json"

echo
echo "Tools ready. Attach with: ./attach-tools.sh"
echo "Library: ${LD_API_HOST}/projects/${LD_PROJECT_KEY}/ai-tools"
