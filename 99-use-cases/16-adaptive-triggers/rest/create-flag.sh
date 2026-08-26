#!/usr/bin/env bash
# Create the dedicated adaptive-trigger string flag, off by default.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

existing="$(api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" 2>/dev/null || true)"
if jq -e '.key' >/dev/null 2>&1 <<<"${existing}"; then
  if [[ "$(jq -r '.variationType // empty' <<<"${existing}")" != "string" ]]; then
    echo "error: ${FLAG_KEY} exists but is not a string flag" >&2
    exit 1
  fi
  echo "String flag ${FLAG_KEY} already exists."
else
  echo "Creating ${FLAG_KEY}..."
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg key "${FLAG_KEY}" \
      '{
        key: $key,
        name: "Enable: adaptive grid highlight",
        description: "Adaptive trigger switches live green highlight to safe none when latency degrades.",
        temporary: false,
        tags: ["grid-navigator", "use-case", "adaptive-triggers", "string"],
        variations: [
          {value: "none", name: "Safe: no highlight", description: "X only"},
          {value: "green", name: "Live: green", description: "Green highlight"}
        ],
        defaults: {onVariation: 1, offVariation: 0}
      }')" | jq '{key, name, variations: [.variations[] | {value, _id}]}'
fi

flag_json="$(fetch_flag)"
none_id="$(variation_id "${flag_json}" "${SAFE_COLOR}")"

echo "Setting ${FLAG_KEY} off with safe variation ${SAFE_COLOR}..."
api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg environmentKey "${LD_ENVIRONMENT_KEY}" \
    --arg variationId "${none_id}" \
    '{
      environmentKey: $environmentKey,
      comment: "16-adaptive-triggers: provision safe default",
      instructions: [
        {kind: "updateOffVariation", variationId: $variationId},
        {kind: "turnFlagOff"}
      ]
    }')" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough}"
