#!/usr/bin/env bash
# Point concise-skeptic (Charlie rewrite) at the rewrite-tier Ollama model
# (default: llama3.1:8b). Judges stay on llama3.2:3b.
# Override: LD_MODEL_REWRITE_ID=qwen2.5:7b ./update-charlie-model.sh
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-variation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

VARIATION_KEY="${1:-concise-skeptic}"

echo "==> Model config for rewrite → ${LD_MODEL_REWRITE_ID}"
"${SCRIPT_DIR}/create-model-config.sh" \
  "$LD_MODEL_REWRITE_CONFIG_KEY" "$LD_MODEL_REWRITE_ID" "$LD_MODEL_REWRITE_DISPLAY_NAME"

BODY="$(jq -n \
  --arg mck "$LD_MODEL_REWRITE_CONFIG_KEY" \
  --arg mid "$LD_MODEL_REWRITE_ID" \
  --arg comment "Charlie rewrite → ${LD_MODEL_REWRITE_ID} (judges remain on ${LD_MODEL_BEST_ID})" \
  '{
    comment: $comment,
    modelConfigKey: $mck,
    model: { modelName: $mid }
  }')"

echo "==> PATCH ${LD_CONFIG_KEY}/${VARIATION_KEY} → ${LD_MODEL_REWRITE_ID}"
api_ok PATCH \
  "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}/variations/${VARIATION_KEY}" \
  -H "Content-Type: application/json" \
  -d "$BODY" \
  | jq '{key, name, modelConfigKey, model}'

echo "Done. Pull locally: ollama pull ${LD_MODEL_REWRITE_ID}"
echo "Restart the demo app so completion_config picks up the new variation."
