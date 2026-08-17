#!/usr/bin/env bash
# Refresh system/user messages on tools-anthropic from rest/messages/*.
# Use after editing message files when the config already exists.
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-variation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

VARIATION_KEY="${1:-$LD_VARIATION_KEY}"
MESSAGES_DIR="${SCRIPT_DIR}/messages"

BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/tools-system.txt" \
  --rawfile user "${MESSAGES_DIR}/tools-user.txt" \
  '{
    comment: "Refresh tools variation messages from repo files",
    messages: [
      { role: "system", content: $sys },
      { role: "user", content: $user }
    ]
  }')"

echo "==> Updating messages on ${LD_CONFIG_KEY}/${VARIATION_KEY}"
api_ok PATCH \
  "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/variations/${VARIATION_KEY}" \
  -H "Content-Type: application/json" \
  -d "$BODY" | jq '{key, name, messages: [.messages[]? | {role, content: (.content | .[0:60] + "…")}]}'

echo "Done."
