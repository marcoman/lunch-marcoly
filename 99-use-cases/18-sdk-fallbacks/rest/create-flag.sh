#!/usr/bin/env bash
# Create the dedicated fallback string flag, live on green.

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
  flag_json="${existing}"
else
  echo "Creating ${FLAG_KEY}..."
  flag_json="$(api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg key "${FLAG_KEY}" \
      '{
        key: $key,
        name: "Enable: SDK fallback grid highlight",
        description: "Dedicated live value for comparing SDK code defaults with last-known streamed flag data.",
        temporary: false,
        tags: ["grid-navigator", "use-case", "sdk-fallbacks", "string"],
        variations: [
          {value: "none", name: "Code default: no highlight", description: "X only"},
          {value: "green", name: "Live: green", description: "Green highlight"}
        ],
        defaults: {onVariation: 1, offVariation: 0}
      }')")"
  jq '{key, name, variations: [.variations[] | {value, _id}]}' <<<"${flag_json}"
fi

none_id="$(variation_id "${flag_json}" "none")"
green_id="$(variation_id "${flag_json}" "green")"
if [[ -z "${none_id}" || -z "${green_id}" ]]; then
  echo "error: ${FLAG_KEY} must contain none and green variations" >&2
  exit 1
fi

echo "Setting off variation none, fallthrough green, and targeting on..."
api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg environmentKey "${LD_ENVIRONMENT_KEY}" \
    --arg noneId "${none_id}" \
    --arg greenId "${green_id}" \
    '{
      environmentKey: $environmentKey,
      comment: "18-sdk-fallbacks: provision live green distinct from code default none",
      instructions: [
        {kind: "updateOffVariation", variationId: $noneId},
        {kind: "updateFallthroughVariationOrRollout", variationId: $greenId},
        {kind: "turnFlagOn"}
      ]
    }')" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough}"
