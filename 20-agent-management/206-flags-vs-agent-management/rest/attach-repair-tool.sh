#!/usr/bin/env bash
# Create the repair Library tool and attach it to Toby's variation only.
# LaunchDarkly: Library tools · patch variation tools
# https://launchdarkly.com/docs/api/agent-control/post-ai-tool
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-variation
# https://launchdarkly.com/docs/home/agentcontrol/tools

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

TOOL_KEY="${LD_REPAIR_TOOL_KEY:-reduce-briefing-uncertainty}"
VARIATION_KEY="${1:-reckless-hype}"
SCHEMA_FILE="${SCRIPT_DIR}/schemas/${TOOL_KEY}.json"

status="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-tools/${TOOL_KEY}")"
if [[ "$status" == "200" ]]; then
  echo "Tool ${TOOL_KEY} already exists — skipping create."
else
  echo "==> Creating tool ${TOOL_KEY}"
  api_ok POST "/projects/${LD_PROJECT_KEY}/ai-tools" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg key "$TOOL_KEY" \
      --slurpfile schema "$SCHEMA_FILE" \
      '{
        key: $key,
        description: "Reduce certainty in a failed equity briefing. The app runs this after a judge fail. The model does not choose to call it.",
        schema: $schema[0],
        tags: ["lunch-marcoly", "flag-compare", "equity-briefing"]
      }')" | jq '{key, description, version}'
fi

TOOL_VER="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-tools/${TOOL_KEY}" | jq -r '.version')"

echo "==> Attaching ${TOOL_KEY} v${TOOL_VER} to ${LD_CONFIG_KEY}/${VARIATION_KEY}"
api_ok PATCH \
  "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/variations/${VARIATION_KEY}" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg key "$TOOL_KEY" \
    --argjson version "$TOOL_VER" \
    '{
      comment: "Attach reduce-briefing-uncertainty. Flag sources have no tool attachment.",
      tools: [{ key: $key, version: $version }]
    }')" | jq '{key, name, tools}'

echo "Done. Toby's reckless-hype variation can repair a failed draft. Charlie's variation is unchanged."
