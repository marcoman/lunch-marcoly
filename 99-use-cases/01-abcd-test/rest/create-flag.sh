#!/usr/bin/env bash
# LaunchDarkly capability: REST API — create ABCD test flag
# See: https://launchdarkly.com/docs/api/feature-flags/post-feature-flag

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

create_flag() {
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d "$1"
}

echo "Creating configure-navigation-count-label..."
create_flag '{
  "key": "configure-navigation-count-label",
  "name": "Configure: navigation count label",
  "description": "ABCD test: string label for navigation move counter.",
  "temporary": false,
  "tags": ["grid-navigator", "use-case", "abcd-test", "configure", "string"],
  "variations": [
    {"value": "Count", "name": "Count", "description": "Variation A"},
    {"value": "Move Count", "name": "Move Count", "description": "Variation B"},
    {"value": "Moves", "name": "Moves", "description": "Variation C"},
    {"value": "Navigation Counts", "name": "Navigation Counts", "description": "Variation D"}
  ],
  "defaults": {"onVariation": 0, "offVariation": 0}
}' | jq '{key, name, tags}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "Setting configure-navigation-count-label to OFF in ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/configure-navigation-count-label" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "{
      \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
      \"comment\": \"ABCD test default: flag off\",
      \"instructions\": [{\"kind\": \"turnFlagOff\"}]
    }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"
fi

echo "Done."
