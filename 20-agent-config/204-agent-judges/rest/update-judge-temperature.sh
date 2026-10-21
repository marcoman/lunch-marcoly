#!/usr/bin/env bash
# Pin both custom judges to temperature=0 (lower run-to-run score variance).
# LaunchDarkly: AgentControl · Judges · PATCH AI Config variation model.parameters
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-variation
# https://launchdarkly.com/docs/home/agentcontrol/judges

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

VARIATION_KEY="${1:-default}"

pin_judge() {
  local key="$1"
  local body

  body="$(jq -n \
    --arg mck "$LD_MODEL_BEST_CONFIG_KEY" \
    --arg mid "$LD_MODEL_BEST_ID" \
    --arg comment "Pin judge sampling temperature=0 for lower score variance" \
    '{
      comment: $comment,
      modelConfigKey: $mck,
      model: {
        modelName: $mid,
        parameters: { temperature: 0 }
      }
    }')"

  echo "==> PATCH ${key}/${VARIATION_KEY} → temperature=0 (${LD_MODEL_BEST_ID})"
  api_ok PATCH \
    "/projects/${LD_PROJECT_KEY}/ai-configs/${key}/variations/${VARIATION_KEY}" \
    -H "Content-Type: application/json" \
    -d "$body" \
    | jq '{key, name, modelConfigKey, model}'
}

pin_judge "$LD_JUDGE_FIDELITY_KEY"
pin_judge "$LD_JUDGE_DISCIPLINE_KEY"

echo "Done. Restart the demo app so create_judge picks up the new parameters."
