#!/usr/bin/env bash
# Create Library tools the capstone app invokes after the specialist draft.
# The checkbox forces the call. The model is not offered the choice.
# LaunchDarkly: AgentControl · Library tools
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
        tags: ["lunch-marcoly", "capstone", "equity-briefing"]
      }')" | jq '{key, description, version}'
}

create_tool \
  "$LD_TOOL_PIG_LATIN" \
  "Convert the specialist draft to Pig Latin. The app calls this; the model cannot skip it." \
  "${SCHEMAS_DIR}/pig-latin.json"

create_tool \
  "$LD_TOOL_ROT13" \
  "Convert the current text with ROT13. Runs after Pig Latin when both are checked." \
  "${SCHEMAS_DIR}/rot13.json"

create_tool \
  "$LD_TOOL_JOKE_TAGLINE" \
  "Append a joke tagline. Runs last so the joke stays readable after the ciphers." \
  "${SCHEMAS_DIR}/joke-tagline.json"

echo
echo "Tools ready. The Node app calls them; there is no attach step."
