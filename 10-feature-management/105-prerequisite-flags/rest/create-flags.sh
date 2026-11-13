#!/usr/bin/env bash
# Create the 105-prerequisite-flags parent and both children, then attach each prerequisite.
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag
# https://launchdarkly.com/docs/home/flags/prereqs
# Keywords: prerequisites, dependent flag, semantic patch, addPrerequisite
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

ensure_flag() {
  local key="$1" body="$2"
  echo "Creating ${key}..."
  local status
  status="$(api_status GET "/flags/${LD_PROJECT_KEY}/${key}")"
  if [[ "$status" == "200" ]]; then
    echo "Flag already exists."
    return
  fi
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d "$body" | jq '{key,name,tags,temporary}'
}

ensure_flag "$PARENT_KEY" '{
  "key": "enable-grid-selection-highlight-prereq",
  "name": "Enable: grid selection highlight (prereq)",
  "description": "105-prerequisite-flags parent. Cites 101-flag-enablement flag enable-grid-selection-highlight (same string highlight: none or a color). Dedicated key so 101 stays independent. Children show-navigation-move-count-prereq and show-anonymous-host-os-emoji-prereq require this flag on and serving green.",
  "temporary": false,
  "tags": ["grid-navigator", "enable", "ui", "string", "prereq"],
  "variations": [
    {"value": "none", "name": "No highlight", "description": "X only — no colors (matches 00-reference-feature)"},
    {"value": "green", "name": "Green", "description": "Green selection highlight"},
    {"value": "yellow", "name": "Yellow", "description": "Yellow selection highlight"},
    {"value": "red", "name": "Red", "description": "Red selection highlight"},
    {"value": "blue", "name": "Blue", "description": "Blue selection highlight"},
    {"value": "purple", "name": "Purple", "description": "Purple selection highlight"}
  ],
  "defaults": {"onVariation": 1, "offVariation": 0}
}'

ensure_flag "$CHILD_KEY" '{
  "key": "show-navigation-move-count-prereq",
  "name": "Show: navigation move count (prereq)",
  "description": "105-prerequisite-flags dependent. Cites 101-flag-enablement flag show-navigation-move-count (same Count: N visibility). Dedicated key. Prerequisite: enable-grid-selection-highlight-prereq on and serving green.",
  "temporary": true,
  "tags": ["grid-navigator", "show", "header", "prerequisite", "prereq"],
  "variations": [
    {"value": true, "name": "Visible", "description": "Display Count: N in the grid header"},
    {"value": false, "name": "Hidden", "description": "Do not display the navigation count"}
  ],
  "defaults": {"onVariation": 0, "offVariation": 1}
}'

ensure_flag "$CHILD_EMOJI_KEY" '{
  "key": "show-anonymous-host-os-emoji-prereq",
  "name": "Show: anonymous host OS emoji (prereq)",
  "description": "105-prerequisite-flags second dependent. Cites 102-flag-variations flag show-anonymous-host-os-emoji (host OS emoji before the username). Dedicated key. Same prerequisite as the count child: enable-grid-selection-highlight-prereq on and serving green. Evaluated on the user context.",
  "temporary": true,
  "tags": ["grid-navigator", "show", "header", "prerequisite", "prereq", "emoji"],
  "variations": [
    {"value": true, "name": "Visible", "description": "Show the host OS emoji before the username"},
    {"value": false, "name": "Hidden", "description": "Do not show the host OS emoji"}
  ],
  "defaults": {"onVariation": 0, "offVariation": 1}
}'

if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "LD_ENVIRONMENT_KEY not set; skipped targeting and prerequisite."
  echo "Done."
  exit 0
fi

echo "Reading parent variation IDs..."
parent_json="$(api GET "/flags/${LD_PROJECT_KEY}/${PARENT_KEY}?env=${LD_ENVIRONMENT_KEY}")"
none_id="$(jq -r '.variations[] | select(.value == "none") | ._id' <<<"$parent_json")"
green_id="$(jq -r '.variations[] | select(.value == "green") | ._id' <<<"$parent_json")"

echo "Turning parent ON with fallthrough green in ${LD_ENVIRONMENT_KEY}..."
api PATCH "/flags/${LD_PROJECT_KEY}/${PARENT_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n --arg env "$LD_ENVIRONMENT_KEY" --arg none "$none_id" --arg green "$green_id" '{
    environmentKey: $env,
    comment: "105-prerequisite-flags: parent on, fallthrough green",
    instructions: [
      {kind: "turnFlagOn"},
      {kind: "updateOffVariation", variationId: $none},
      {kind: "updateFallthroughVariationOrRollout", variationId: $green}
    ]
  }')" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough}"

attach_child() {
  local key="$1"
  local child_json true_id false_id has_prereq prereq_kind
  child_json="$(api GET "/flags/${LD_PROJECT_KEY}/${key}?env=${LD_ENVIRONMENT_KEY}")"
  true_id="$(jq -r '.variations[] | select(.value == true) | ._id' <<<"$child_json")"
  false_id="$(jq -r '.variations[] | select(.value == false) | ._id' <<<"$child_json")"
  has_prereq="$(jq --arg env "$LD_ENVIRONMENT_KEY" --arg parent "$PARENT_KEY" '
    (.environments[$env].prerequisites // [])
    | map(select(.key == $parent))
    | length > 0
  ' <<<"$child_json")"
  if [[ "$has_prereq" == "true" ]]; then
    prereq_kind="updatePrerequisite"
    echo "Updating ${key} prerequisite to parent/green..."
  else
    prereq_kind="addPrerequisite"
    echo "Adding ${key} prerequisite (parent must serve green)..."
  fi
  echo "Turning ${key} ON with fallthrough true in ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/${key}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "$(jq -n \
      --arg env "$LD_ENVIRONMENT_KEY" \
      --arg parent "$PARENT_KEY" \
      --arg green "$green_id" \
      --arg vis "$true_id" \
      --arg hid "$false_id" \
      --arg prereq "$prereq_kind" \
      --arg key "$key" \
      '{
        environmentKey: $env,
        comment: ("105-prerequisite-flags: " + $key + " on; prerequisite parent/green"),
        instructions: [
          {kind: "turnFlagOn"},
          {kind: "updateOffVariation", variationId: $hid},
          {kind: "updateFallthroughVariationOrRollout", variationId: $vis},
          {kind: $prereq, key: $parent, variationId: $green}
        ]
      }')" | jq --arg key "$key" --arg env "$LD_ENVIRONMENT_KEY" \
        '{key: $key} + (.environments[$env] | {on, offVariation, fallthrough, prerequisites})'
}

attach_child "$CHILD_KEY"
attach_child "$CHILD_EMOJI_KEY"

echo "Done."
