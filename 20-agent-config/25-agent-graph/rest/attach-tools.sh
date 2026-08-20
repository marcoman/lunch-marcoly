#!/usr/bin/env bash
# Attach scorer Library tools to questions + joke agent nodes.
# LaunchDarkly: PATCH variation tools
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-variation
# https://launchdarkly.com/docs/home/agentcontrol/tools

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

: "${LD_TOOL_QUESTION_GAP:=score-question-gap}"
: "${LD_TOOL_JOKE_CORNY:=score-joke-corny}"

tool_version() {
  local key="$1"
  api_ok GET "/projects/${LD_PROJECT_KEY}/ai-tools/${key}" | jq -r '.version'
}

attach_one() {
  local config_key="$1"
  local tool_key="$2"
  local tool_ver="$3"

  local cfg vkey
  cfg="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${config_key}")"
  vkey="$(echo "$cfg" | jq -r '.variations[0].key // "default"')"

  echo "==> ${config_key}/${vkey} ← ${tool_key} v${tool_ver}"
  api_ok PATCH \
    "/projects/${LD_PROJECT_KEY}/ai-configs/${config_key}/variations/${vkey}" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg tkey "$tool_key" \
      --argjson tver "$tool_ver" \
      '{
        comment: ("Attach " + $tkey + " for Trace scoring demo"),
        tools: [{ key: $tkey, version: $tver }]
      }')" | jq '{key, name, tools}'
}

Q_VER="$(tool_version "$LD_TOOL_QUESTION_GAP")"
J_VER="$(tool_version "$LD_TOOL_JOKE_CORNY")"

attach_one "$LD_NODE_QUESTIONS" "$LD_TOOL_QUESTION_GAP" "$Q_VER"
attach_one "$LD_NODE_JOKE" "$LD_TOOL_JOKE_CORNY" "$J_VER"

echo "Done."
