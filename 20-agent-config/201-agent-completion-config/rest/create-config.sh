#!/usr/bin/env bash
# LaunchDarkly capability: AgentControl — create completion config + variations + fallthrough
# Creates equity-briefing-completion (completion mode) with three variations, each on its
# own Ollama model tier:
#   baseline-analyst  → gemma2:2b     (default / Neutral Nancy + Amelia fallthrough)
#   concise-skeptic   → llama3.2:3b   (best / Conservative Charlie)
#   reckless-hype     → llama3.2:1b   (simple / Thoughtless Toby)
# Then points environment fallthrough at baseline-analyst so the SDK returns enabled=true.
# https://launchdarkly.com/docs/api/agent-control/post-ai-config
# https://launchdarkly.com/docs/api/agent-control/post-ai-config-variation
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-targeting
# https://launchdarkly.com/docs/home/agentcontrol/quickstart

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"

# 1) Ensure all three custom Ollama model configs exist (idempotent).
echo "==> Model configs (best / default / simple)"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_BEST_CONFIG_KEY" "$LD_MODEL_BEST_ID" "$LD_MODEL_BEST_DISPLAY_NAME"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_DEFAULT_CONFIG_KEY" "$LD_MODEL_DEFAULT_ID" "$LD_MODEL_DEFAULT_DISPLAY_NAME"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_SIMPLE_CONFIG_KEY" "$LD_MODEL_SIMPLE_ID" "$LD_MODEL_SIMPLE_DISPLAY_NAME"

# 2) Create the completion config with defaultVariation = baseline-analyst (middle tier).
STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}")"
if [[ "$STATUS" == "200" ]]; then
  echo "error: AI config ${LD_CONFIG_KEY} already exists." >&2
  echo "Delete it first: ./delete-config.sh ${LD_CONFIG_KEY}" >&2
  exit 1
fi

echo "==> AI config ${LD_CONFIG_KEY} (mode=completion, defaultVariation=baseline-analyst → ${LD_MODEL_DEFAULT_ID})"
CREATE_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/baseline-system.txt" \
  --rawfile user "${MESSAGES_DIR}/baseline-user.txt" \
  --arg key "$LD_CONFIG_KEY" \
  --arg name "$LD_CONFIG_NAME" \
  --arg mck "$LD_MODEL_DEFAULT_CONFIG_KEY" \
  --arg mid "$LD_MODEL_DEFAULT_ID" \
  '{
    key: $key,
    name: $name,
    description: "Completion config for the equity briefing agent: model + system/user messages from LaunchDarkly. Per-persona Ollama tiers: Charlie=llama3.2:3b (best), Nancy/Amelia=gemma2:2b (default), Toby=llama3.2:1b (simple).",
    mode: "completion",
    tags: ["lunch-marcoly", "agent-completion", "equity-briefing"],
    defaultVariation: {
      key: "baseline-analyst",
      name: "baseline-analyst",
      modelConfigKey: $mck,
      model: { modelName: $mid },
      messages: [
        { role: "system", content: $sys },
        { role: "user", content: $user }
      ]
    }
  }')"

api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs" \
  -H "Content-Type: application/json" \
  -d "$CREATE_BODY" | jq '{key, name, mode, tags, variations: [.variations[]? | {key, name, modelConfigKey}]}'

# 3) Add concise-skeptic (Charlie) on the best-tier model.
echo "==> Variation concise-skeptic → ${LD_MODEL_BEST_ID} (best)"
SKEPTIC_BODY="$(jq -n \
  --rawfile sys "${MESSAGES_DIR}/skeptic-system.txt" \
  --rawfile user "${MESSAGES_DIR}/skeptic-user.txt" \
  --arg mck "$LD_MODEL_BEST_CONFIG_KEY" \
  --arg mid "$LD_MODEL_BEST_ID" \
  '{
    key: "concise-skeptic",
    name: "concise-skeptic",
    modelConfigKey: $mck,
    model: { modelName: $mid },
    messages: [
      { role: "system", content: $sys },
      { role: "user", content: $user }
    ]
  }')"

api_ok POST "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/variations" \
  -H "Content-Type: application/json" \
  -d "$SKEPTIC_BODY" | jq '{key, name, modelConfigKey, model}'

# 3b) Add reckless-hype (Toby) on the simple-tier model.
echo "==> Variation reckless-hype → ${LD_MODEL_SIMPLE_ID} (simple)"
"${SCRIPT_DIR}/create-variation-reckless-hype.sh"

# 4) Point fallthrough at baseline-analyst (required — fresh configs serve a disabled variation).
if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "==> Targeting fallthrough → baseline-analyst (${LD_ENVIRONMENT_KEY})"
  "${SCRIPT_DIR}/update-targeting.sh" baseline-analyst
  echo "==> Optional name rules: ./update-name-targeting.sh (Charlie/Nancy/Toby)"
else
  echo "warning: LD_ENVIRONMENT_KEY unset — skip targeting." >&2
  echo "  The SDK will return enabled=false until fallthrough points at baseline-analyst." >&2
  echo "  Run: export LD_ENVIRONMENT_KEY=test && ./update-targeting.sh baseline-analyst" >&2
fi

echo "Done. Config key: ${LD_CONFIG_KEY}"
echo "Models: Charlie=${LD_MODEL_BEST_ID}  Nancy/Amelia=${LD_MODEL_DEFAULT_ID}  Toby=${LD_MODEL_SIMPLE_ID}"
echo "Pull locally when ready:"
echo "  ollama pull ${LD_MODEL_BEST_ID}"
echo "  ollama pull ${LD_MODEL_DEFAULT_ID}"
echo "  ollama pull ${LD_MODEL_SIMPLE_ID}"
echo "UI: ${LD_API_HOST}/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}"
