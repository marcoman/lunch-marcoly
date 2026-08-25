#!/usr/bin/env bash
# LaunchDarkly capability: REST API — create client-side-available feature flags
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag
# Keywords: client-side availability, usingEnvironmentId, string variation, boolean variation

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

echo "Creating enable-client-grid-highlight (client-side SDK available)..."
create_flag '{
  "key": "enable-client-grid-highlight",
  "name": "Enable: client grid highlight",
  "description": "Browser-evaluated string flag. Off serves none (X only). On serves the fallthrough color. Must be available to client-side SDKs.",
  "temporary": false,
  "tags": ["grid-navigator", "client-sdk", "enable", "ui", "string"],
  "clientSideAvailability": {
    "usingEnvironmentId": true,
    "usingMobileKey": false
  },
  "variations": [
    { "value": "none", "name": "No highlight", "description": "X only — matches 02-reference-client-code" },
    { "value": "green", "name": "Green", "description": "Green selection highlight" },
    { "value": "yellow", "name": "Yellow", "description": "Yellow selection highlight" },
    { "value": "red", "name": "Red", "description": "Red selection highlight" },
    { "value": "blue", "name": "Blue", "description": "Blue selection highlight" },
    { "value": "purple", "name": "Purple", "description": "Purple selection highlight" }
  ],
  "defaults": { "onVariation": 1, "offVariation": 0 }
}' | jq '{key, name, tags, clientSideAvailability}'

echo "Creating show-client-move-count (client-side SDK available)..."
create_flag '{
  "key": "show-client-move-count",
  "name": "Show: client move count",
  "description": "Browser-evaluated boolean flag. When on, the grid header shows Count: N. Must be available to client-side SDKs.",
  "temporary": true,
  "tags": ["grid-navigator", "client-sdk", "show", "header"],
  "clientSideAvailability": {
    "usingEnvironmentId": true,
    "usingMobileKey": false
  },
  "variations": [
    { "value": true, "name": "Visible", "description": "Display Count: N" },
    { "value": false, "name": "Hidden", "description": "Hide the navigation count" }
  ],
  "defaults": { "onVariation": 0, "offVariation": 1 }
}' | jq '{key, name, tags, clientSideAvailability}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "Turning both flags OFF in ${LD_ENVIRONMENT_KEY}..."
  for key in enable-client-grid-highlight show-client-move-count; do
    api PATCH "/flags/${LD_PROJECT_KEY}/${key}" \
      -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
      -d "{
        \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
        \"comment\": \"31-client-evaluation default: off\",
        \"instructions\": [{\"kind\": \"turnFlagOff\"}]
      }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation}"
  done
fi

echo "Done."
