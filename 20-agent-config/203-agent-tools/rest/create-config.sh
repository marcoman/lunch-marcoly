#!/usr/bin/env bash
# LaunchDarkly: create equity-briefing-tools (completion mode + Anthropic)
# https://launchdarkly.com/docs/api/agent-control/post-ai-config
# https://launchdarkly.com/docs/home/agentcontrol/tools

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"

echo "==> Ensuring Library tools exist"
"${SCRIPT_DIR}/create-tools.sh"

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}")"
if [[ "$STATUS" == "200" ]]; then
  echo "error: AI config ${LD_CONFIG_KEY} already exists." >&2
  echo "Delete it first: ./delete-config.sh ${LD_CONFIG_KEY}" >&2
  exit 1
fi

echo "==> AI config ${LD_CONFIG_KEY} (defaultVariation=${LD_VARIATION_KEY} → ${LD_ANTHROPIC_MODEL_ID})"
CREATE_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/tools-system.txt" \
  --rawfile user "${MESSAGES_DIR}/tools-user.txt" \
  --arg key "$LD_CONFIG_KEY" \
  --arg name "$LD_CONFIG_NAME" \
  --arg vkey "$LD_VARIATION_KEY" \
  --arg mid "$LD_ANTHROPIC_MODEL_ID" \
  '{
    key: $key,
    name: $name,
    description: "Completion config for 23-agent-tools: Library tools analyze-ticker-stories + compare-ticker-analyses. Anthropic for reliable tool calling.",
    mode: "completion",
    tags: ["lunch-marcoly", "agent-tools", "equity-briefing"],
    defaultVariation: {
      key: $vkey,
      name: $vkey,
      model: { modelName: $mid },
      messages: [
        { role: "system", content: $sys },
        { role: "user", content: $user }
      ]
    }
  }')"

api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs" \
  -H "Content-Type: application/json" \
  -d "$CREATE_BODY" | jq '{key, name, mode, tags, variations: [.variations[]? | {key, name}]}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "==> Targeting fallthrough → ${LD_VARIATION_KEY} (${LD_ENVIRONMENT_KEY})"
  "${SCRIPT_DIR}/update-targeting.sh" "$LD_VARIATION_KEY"
fi

echo "==> Attaching Library tools"
"${SCRIPT_DIR}/attach-tools.sh"

echo
echo "Created ${LD_CONFIG_KEY}."
echo "UI: ${LD_API_HOST}/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}"
echo "Requires ANTHROPIC_API_KEY for generate."
