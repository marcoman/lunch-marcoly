#!/usr/bin/env bash
# Attach analyze + compare Library tools to the tools variation.
# LaunchDarkly: PATCH variation tools / toolKeys only
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-variation
# https://launchdarkly.com/docs/home/agentcontrol/tools

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

VARIATION_KEY="${1:-$LD_VARIATION_KEY}"

tool_version() {
  local key="$1"
  api_ok GET "/projects/${LD_PROJECT_KEY}/ai-tools/${key}" | jq -r '.version'
}

ANALYZE_VER="$(tool_version "$LD_TOOL_ANALYZE_KEY")"
COMPARE_VER="$(tool_version "$LD_TOOL_COMPARE_KEY")"

echo "==> Attaching tools to ${LD_CONFIG_KEY}/${VARIATION_KEY}"
echo "  ${LD_TOOL_ANALYZE_KEY} v${ANALYZE_VER}"
echo "  ${LD_TOOL_COMPARE_KEY} v${COMPARE_VER}"

# Pass only tools — do not clobber messages/model from the UI.
BODY="$(jq -n \
  --arg akey "$LD_TOOL_ANALYZE_KEY" \
  --argjson aver "$ANALYZE_VER" \
  --arg ckey "$LD_TOOL_COMPARE_KEY" \
  --argjson cver "$COMPARE_VER" \
  '{
    comment: "Attach analyze-ticker-stories + compare-ticker-analyses",
    tools: [
      { key: $akey, version: $aver },
      { key: $ckey, version: $cver }
    ]
  }')"

api_ok PATCH \
  "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/variations/${VARIATION_KEY}" \
  -H "Content-Type: application/json" \
  -d "$BODY" | jq '{key, name, tools}'

echo "Done."
