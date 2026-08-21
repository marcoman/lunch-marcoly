#!/usr/bin/env bash
# Create the highlight string flag (off by default in the target environment).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

is_string_highlight_flag() {
  local flag_json="$1"
  local vtype
  vtype="$(echo "${flag_json}" | jq -r '.variationType // empty')"
  if [[ "${vtype}" == "string" ]]; then
    return 0
  fi
  echo "${flag_json}" | jq -e '.variations[0].value == "none"' >/dev/null 2>&1
}

ensure_string_flag() {
  local existing
  if existing="$(api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" 2>/dev/null || true)"; then
    if echo "${existing}" | jq -e '.key' >/dev/null 2>&1; then
      if is_string_highlight_flag "${existing}"; then
        echo "String flag ${FLAG_KEY} already exists."
        return 0
      fi
      echo "Flag ${FLAG_KEY} is not a string flag; replacing..."
      api DELETE "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" >/dev/null
    fi
  fi

  echo "Creating ${FLAG_KEY} (string)..."
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
      "key": "enable-grid-selection-highlight",
      "name": "Enable: grid selection highlight",
      "description": "Progressive rollout example: highlight color for selected grid cell.",
      "temporary": false,
      "tags": ["grid-navigator", "use-case", "progressive-rollout", "configure", "string"],
      "variations": [
        {"value": "none", "name": "No highlight", "description": "X only"},
        {"value": "green", "name": "Green", "description": "Green highlight"},
        {"value": "yellow", "name": "Yellow", "description": "Yellow highlight"},
        {"value": "red", "name": "Red", "description": "Red highlight"},
        {"value": "blue", "name": "Blue", "description": "Blue highlight"},
        {"value": "purple", "name": "Purple", "description": "Purple highlight"}
      ],
      "defaults": {"onVariation": 1, "offVariation": 0}
    }' | jq '{key, name, variations: [.variations[] | {value, _id}]}'
}

set_flag_off() {
  echo "Setting ${FLAG_KEY} to OFF in ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "{
      \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
      \"comment\": \"Progressive rollout default: flag off\",
      \"instructions\": [{\"kind\": \"turnFlagOff\"}]
    }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough}"
}

ensure_string_flag
set_flag_off

echo "Done."
