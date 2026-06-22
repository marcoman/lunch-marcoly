#!/usr/bin/env bash
# Create segments and string highlight flag for segments-by-name use case.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

FLAG_KEY="configure-grid-selection-green-highlight"

variation_id() {
  local flag_json="$1"
  local value="$2"
  echo "${flag_json}" | jq -r --arg v "${value}" '.variations[] | select(.value == $v) | ._id' | head -1
}

is_string_highlight_flag() {
  local flag_json="$1"
  local vtype
  vtype="$(echo "${flag_json}" | jq -r '.variationType // empty')"
  if [[ "${vtype}" == "string" ]]; then
    return 0
  fi
  # API sometimes omits variationType; infer from first variation value.
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
      "key": "configure-grid-selection-green-highlight",
      "name": "Configure: grid selection green highlight",
      "description": "Segments-by-name: highlight color from segment targeting.",
      "temporary": false,
      "tags": ["grid-navigator", "use-case", "segments-by-name", "configure", "string"],
      "variations": [
        {"value": "none", "name": "No highlight", "description": "X only"},
        {"value": "yellow", "name": "Yellow", "description": "Yellow highlight"},
        {"value": "red", "name": "Red", "description": "Red highlight"},
        {"value": "blue", "name": "Blue", "description": "Blue highlight"},
        {"value": "green", "name": "Green", "description": "Green highlight"},
        {"value": "purple", "name": "Purple", "description": "Purple highlight"}
      ],
      "defaults": {"onVariation": 0, "offVariation": 0}
    }' | jq '{key, name, variations: [.variations[] | {value, _id}]}'
}

configure_targeting() {
  echo "Configuring segment targeting (flag ON)..."
  local flag_json
  flag_json="$(api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}")"

  local vid_none vid_yellow vid_red vid_blue vid_green vid_purple
  vid_none="$(variation_id "${flag_json}" "none")"
  vid_yellow="$(variation_id "${flag_json}" "yellow")"
  vid_red="$(variation_id "${flag_json}" "red")"
  vid_blue="$(variation_id "${flag_json}" "blue")"
  vid_green="$(variation_id "${flag_json}" "green")"
  vid_purple="$(variation_id "${flag_json}" "purple")"

  if [[ -z "${vid_none}" || -z "${vid_red}" ]]; then
    echo "error: could not read variation IDs from flag (is it a string flag?)" >&2
    exit 1
  fi

  local patch_body
  patch_body="$(jq -n \
    --arg env "${LD_ENVIRONMENT_KEY}" \
    --arg none "${vid_none}" \
    --arg yellow "${vid_yellow}" \
    --arg red "${vid_red}" \
    --arg blue "${vid_blue}" \
    --arg green "${vid_green}" \
    --arg purple "${vid_purple}" \
    '{
      environmentKey: $env,
      comment: "Segments-by-name targeting",
      instructions: [
        {kind: "turnFlagOn"},
        {kind: "replaceRules", rules: [
          {description: "Generic", variationId: $none, clauses: [{contextKind: "user", attribute: "segmentMatch", op: "segmentMatch", values: ["seg-by-name-generic"]}]},
          {description: "Color yellow", variationId: $yellow, clauses: [{contextKind: "user", attribute: "segmentMatch", op: "segmentMatch", values: ["seg-by-name-color-yellow"]}]},
          {description: "Color red", variationId: $red, clauses: [{contextKind: "user", attribute: "segmentMatch", op: "segmentMatch", values: ["seg-by-name-color-red"]}]},
          {description: "Color blue", variationId: $blue, clauses: [{contextKind: "user", attribute: "segmentMatch", op: "segmentMatch", values: ["seg-by-name-color-blue"]}]},
          {description: "Color green", variationId: $green, clauses: [{contextKind: "user", attribute: "segmentMatch", op: "segmentMatch", values: ["seg-by-name-color-green"]}]},
          {description: "Color purple", variationId: $purple, clauses: [{contextKind: "user", attribute: "segmentMatch", op: "segmentMatch", values: ["seg-by-name-color-purple"]}]},
          {description: "Human beta", variationId: $green, clauses: [{contextKind: "user", attribute: "segmentMatch", op: "segmentMatch", values: ["seg-by-name-human-beta"]}]},
          {description: "Robot beta", variationId: $purple, clauses: [{contextKind: "user", attribute: "segmentMatch", op: "segmentMatch", values: ["seg-by-name-robot-beta"]}]},
          {description: "Human", variationId: $yellow, clauses: [{contextKind: "user", attribute: "segmentMatch", op: "segmentMatch", values: ["seg-by-name-human"]}]},
          {description: "Robot", variationId: $red, clauses: [{contextKind: "user", attribute: "segmentMatch", op: "segmentMatch", values: ["seg-by-name-robot"]}]}
        ]},
        {kind: "updateFallthroughVariationOrRollout", variationId: $none}
      ]
    }')"

  api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "${patch_body}" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, rules: (.rules | length), fallthrough}"
}

echo "Creating segments (environment: ${LD_ENVIRONMENT_KEY})..."
ensure_segment "seg-by-name-generic" "By name: generic" "segmentType" '["generic"]'
for color in yellow red blue green purple; do
  ensure_segment "seg-by-name-color-${color}" "By name: color ${color}" "namedColor" "[\"${color}\"]"
done
ensure_segment "seg-by-name-human" "By name: human" "segmentType" '["human"]'
ensure_segment "seg-by-name-robot" "By name: robot" "segmentType" '["robot"]'
ensure_segment "seg-by-name-human-beta" "By name: human + beta" "segmentType" '["human-beta"]'
ensure_segment "seg-by-name-robot-beta" "By name: robot + beta" "segmentType" '["robot-beta"]'

ensure_string_flag
configure_targeting

echo "Done."
