#!/usr/bin/env bash
# Create Library tools for 25-agent-graph scorers (Trace teaching).
# LaunchDarkly: AgentControl · Library tools
# https://launchdarkly.com/docs/api/agent-control/post-ai-tool
# https://launchdarkly.com/docs/home/agentcontrol/tools

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

SCHEMAS_DIR="${SCRIPT_DIR}/schemas"

: "${LD_TOOL_QUESTION_GAP:=score-question-gap}"
: "${LD_TOOL_JOKE_CORNY:=score-joke-corny}"

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
        tags: ["lunch-marcoly", "agent-graph", "equity-briefing"]
      }')" | jq '{key, description, version}'
}

create_tool \
  "$LD_TOOL_QUESTION_GAP" \
  "Score one follow-up question against headlines. Returns gap and ground scores in [0,1] (decimals). Does not change the specialist text — teaching Trace visibility." \
  "${SCHEMAS_DIR}/score-question-gap.json"

create_tool \
  "$LD_TOOL_JOKE_CORNY" \
  "Score a joke for corniness in [0,1]. Easter-egg Trace metric; does not rewrite the joke." \
  "${SCHEMAS_DIR}/score-joke-corny.json"

echo
echo "Tools ready. Attach with: ./attach-tools.sh"
echo "Library: ${LD_API_HOST}/projects/${LD_PROJECT_KEY}/ai-tools"
