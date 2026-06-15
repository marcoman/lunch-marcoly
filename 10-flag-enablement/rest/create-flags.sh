#!/usr/bin/env bash
# LaunchDarkly capability: REST API — create feature flags
# Creates both grid navigator flags with variations, tags, and defaults.
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

echo "Creating configure-grid-selection-green-highlight..."
create_flag '{
  "key": "configure-grid-selection-green-highlight",
  "name": "Configure: grid selection green highlight",
  "description": "When enabled, the selected grid cell shows a colored highlight (default pink) in addition to the X marker. Default is X only with no colors.",
  "temporary": false,
  "tags": ["grid-navigator", "configure", "ui"],
  "variations": [
    {
      "value": true,
      "name": "Highlight enabled",
      "description": "Selected cell shows X with colored highlight (pink by default, or context color when context flag is on)"
    },
    {
      "value": false,
      "name": "X only",
      "description": "Selected cell shows X with no colors (matches 00-reference)"
    }
  ],
  "defaults": {
    "onVariation": 0,
    "offVariation": 1
  }
}' | jq '{key, name, tags, temporary}'

echo "Creating configure-grid-selection-context-highlight..."
create_flag '{
  "key": "configure-grid-selection-context-highlight",
  "name": "Configure: grid selection context highlight",
  "description": "When enabled with the highlight flag, selection and username colors follow cohort rules parsed from the login name (human, robot, beta). When off, highlight uses pink.",
  "temporary": false,
  "tags": ["grid-navigator", "configure", "ui", "context"],
  "variations": [
    {
      "value": true,
      "name": "Context colors",
      "description": "Apply cohort-based highlight and username colors from login name"
    },
    {
      "value": false,
      "name": "Default pink",
      "description": "Use pink highlight when highlight flag is on"
    }
  ],
  "defaults": {
    "onVariation": 0,
    "offVariation": 1
  }
}' | jq '{key, name, tags, temporary}'

echo "Creating show-navigation-move-count..."
create_flag '{
  "key": "show-navigation-move-count",
  "name": "Show: navigation move count",
  "description": "When enabled, the grid header displays Count: N where N is the number of successful navigation moves. Default is hidden.",
  "temporary": true,
  "tags": ["grid-navigator", "show", "header"],
  "variations": [
    {
      "value": true,
      "name": "Visible",
      "description": "Display Count: N in the grid header"
    },
    {
      "value": false,
      "name": "Hidden",
      "description": "Do not display the navigation count"
    }
  ],
  "defaults": {
    "onVariation": 0,
    "offVariation": 1
  }
}' | jq '{key, name, tags, temporary}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "Setting show-navigation-move-count to OFF in environment ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/show-navigation-move-count" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "{
      \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
      \"comment\": \"Default: navigation count hidden\",
      \"instructions\": [{\"kind\": \"turnFlagOff\"}]
    }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"

  echo "Setting configure-grid-selection-context-highlight to OFF in environment ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/configure-grid-selection-context-highlight" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "{
      \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
      \"comment\": \"Default: context colors off (pink when highlight on)\",
      \"instructions\": [{\"kind\": \"turnFlagOff\"}]
    }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"

  echo "Setting configure-grid-selection-green-highlight to OFF in environment ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/configure-grid-selection-green-highlight" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "{
      \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
      \"comment\": \"Default: X only, no colors\",
      \"instructions\": [{\"kind\": \"turnFlagOff\"}]
    }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"
fi

echo "Done."
