#!/usr/bin/env bash
# LaunchDarkly capability: REST API — create mobile-SDK-available feature flags
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag
# Keywords: client-side availability, usingMobileKey, string variation, boolean variation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

create_flag() {
  local body="$1"
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d "$body"
}

echo "Creating enable-mobile-grid-highlight (mobile SDK available)..."
create_flag '{
  "key": "enable-mobile-grid-highlight",
  "name": "Enable: mobile grid highlight",
  "description": "Device-evaluated string flag. Off serves none (X only). On serves the fallthrough color. Must be available to mobile SDKs.",
  "temporary": false,
  "tags": ["grid-navigator", "mobile-sdk", "enable", "ui", "string"],
  "clientSideAvailability": {
    "usingEnvironmentId": true,
    "usingMobileKey": true
  },
  "variations": [
    { "value": "none", "name": "No highlight", "description": "X only — matches 51-reference" },
    { "value": "green", "name": "Green", "description": "Green selection highlight" },
    { "value": "yellow", "name": "Yellow", "description": "Yellow selection highlight" },
    { "value": "red", "name": "Red", "description": "Red selection highlight" },
    { "value": "blue", "name": "Blue", "description": "Blue selection highlight" },
    { "value": "purple", "name": "Purple", "description": "Purple selection highlight" }
  ],
  "defaults": { "onVariation": 1, "offVariation": 0 }
}' | jq '{key, name, tags, clientSideAvailability}'

echo "Creating show-mobile-move-count (mobile SDK available)..."
create_flag '{
  "key": "show-mobile-move-count",
  "name": "Show: mobile move count",
  "description": "Device-evaluated boolean flag. When on, the grid header shows Count: N. Must be available to mobile SDKs.",
  "temporary": true,
  "tags": ["grid-navigator", "mobile-sdk", "show", "header"],
  "clientSideAvailability": {
    "usingEnvironmentId": true,
    "usingMobileKey": true
  },
  "variations": [
    { "value": true, "name": "Visible", "description": "Display Count: N" },
    { "value": false, "name": "Hidden", "description": "Hide the navigation count" }
  ],
  "defaults": { "onVariation": 0, "offVariation": 1 }
}' | jq '{key, name, tags, clientSideAvailability}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "Turning both flags OFF in ${LD_ENVIRONMENT_KEY}..."
  for key in enable-mobile-grid-highlight show-mobile-move-count; do
    api PATCH "/flags/${LD_PROJECT_KEY}/${key}" \
      -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
      -d "{
        \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
        \"comment\": \"52-mobile-evaluation default: off\",
        \"instructions\": [{\"kind\": \"turnFlagOff\"}]
      }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation}"
  done
fi

echo "Done."
