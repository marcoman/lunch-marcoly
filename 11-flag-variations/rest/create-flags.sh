#!/usr/bin/env bash
# LaunchDarkly capability: REST API — create feature flags
# Creates all four flag-variations flags with variations, tags, and defaults.
# See: https://launchdarkly.com/docs/api/feature-flags/post-feature-flag

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

echo "Creating show-anonymous-host-os-emoji..."
create_flag '{
  "key": "show-anonymous-host-os-emoji",
  "name": "Show: anonymous host OS emoji",
  "description": "When enabled, displays an OS emoji before the username. Evaluated with an anonymous context and private hostOs attribute.",
  "temporary": true,
  "tags": ["grid-navigator", "show", "header", "anonymous", "private-attributes"],
  "variations": [
    {"value": true, "name": "Visible", "description": "Show OS emoji before username"},
    {"value": false, "name": "Hidden", "description": "No OS emoji (default)"}
  ],
  "defaults": {"onVariation": 0, "offVariation": 1}
}' | jq '{key, name, tags, temporary}'

echo "Creating configure-navigation-count-label..."
create_flag '{
  "key": "configure-navigation-count-label",
  "name": "Configure: navigation count label",
  "description": "String label prefix for the navigation move counter in the header.",
  "temporary": false,
  "tags": ["grid-navigator", "configure", "header", "string"],
  "variations": [
    {"value": "Count", "name": "Count", "description": "Display Count: N (default)"},
    {"value": "Move Count", "name": "Move Count", "description": "Display Move Count: N"},
    {"value": "Moves", "name": "Moves", "description": "Display Moves: N"},
    {"value": "Navigation Counts", "name": "Navigation Counts", "description": "Display Navigation Counts: N"}
  ],
  "defaults": {"onVariation": 0, "offVariation": 0}
}' | jq '{key, name, tags, temporary}'

echo "Creating configure-lucky-number..."
create_flag '{
  "key": "configure-lucky-number",
  "name": "Configure: lucky number",
  "description": "Numeric value displayed in the header as Lucky Number is: N.",
  "temporary": false,
  "tags": ["grid-navigator", "configure", "header", "number"],
  "variations": [
    {"value": 0, "name": "Zero", "description": "Lucky Number is: 0 (default)"},
    {"value": 1, "name": "One", "description": "Lucky Number is: 1"},
    {"value": 2, "name": "Two", "description": "Lucky Number is: 2"},
    {"value": 3, "name": "Three", "description": "Lucky Number is: 3"},
    {"value": 4, "name": "Four", "description": "Lucky Number is: 4"},
    {"value": 5, "name": "Five", "description": "Lucky Number is: 5"}
  ],
  "defaults": {"onVariation": 0, "offVariation": 0}
}' | jq '{key, name, tags, temporary}'

echo "Creating configure-max-navigation-moves..."
create_flag '{
  "key": "configure-max-navigation-moves",
  "name": "Configure: max navigation moves",
  "description": "JSON object with maxMoves limiting successful navigation moves per grid session.",
  "temporary": false,
  "tags": ["grid-navigator", "configure", "navigation", "json"],
  "variations": [
    {"value": {"maxMoves": 100}, "name": "Standard (100)", "description": "Standard users: 100 total moves"},
    {"value": {"maxMoves": 10}, "name": "Limited (10)", "description": "Short limit for testing"},
    {"value": {"maxMoves": 1000}, "name": "Extended (1000)", "description": "High limit"}
  ],
  "defaults": {"onVariation": 0, "offVariation": 0}
}' | jq '{key, name, tags, temporary}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "Setting show-anonymous-host-os-emoji to OFF in environment ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/show-anonymous-host-os-emoji" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "{
      \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
      \"comment\": \"Default: no anonymous OS emoji\",
      \"instructions\": [{\"kind\": \"turnFlagOff\"}]
    }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"

  for key in configure-navigation-count-label configure-lucky-number configure-max-navigation-moves; do
    echo "Setting ${key} to ON (default variation) in environment ${LD_ENVIRONMENT_KEY}..."
    api PATCH "/flags/${LD_PROJECT_KEY}/${key}" \
      -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
      -d "{
        \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
        \"comment\": \"Default variation active\",
        \"instructions\": [{\"kind\": \"turnFlagOn\"}]
      }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"
  done
fi

echo "Done."
