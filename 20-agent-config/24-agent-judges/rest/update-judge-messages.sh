#!/usr/bin/env bash
# Refresh system messages on both custom judges from rest/messages/*.
# Use after editing judge-*-system.txt when the judges already exist.
# LaunchDarkly: AgentControl · Judges · PATCH AI Config variation
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-variation
# https://launchdarkly.com/docs/home/agentcontrol/judges

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"
VARIATION_KEY="${1:-default}"

update_judge() {
  local key="$1"
  local sys_file="$2"
  local body

  body="$(jq -n \
    --rawfile sys "${MESSAGES_DIR}/${sys_file}" \
    --arg comment "Refresh ${key} judge system prompt from repo (score anchors)" \
    '{
      comment: $comment,
      messages: [
        { role: "system", content: $sys }
      ]
    }')"

  echo "==> Updating messages on ${key}/${VARIATION_KEY}"
  api_ok PATCH \
    "/projects/${LD_PROJECT_KEY}/ai-configs/${key}/variations/${VARIATION_KEY}" \
    -H "Content-Type: application/json" \
    -d "$body" \
    | jq '{key, name, messages: [.messages[]? | {role, content: (.content | .[0:80] + "…")}]}'
}

update_judge "$LD_JUDGE_FIDELITY_KEY" "judge-source-fidelity-system.txt"
update_judge "$LD_JUDGE_DISCIPLINE_KEY" "judge-recommendation-discipline-system.txt"

echo "Done. Restart the demo app so create_judge picks up the new variation."
