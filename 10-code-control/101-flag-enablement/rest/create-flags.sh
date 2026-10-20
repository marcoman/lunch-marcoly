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

echo "Creating enable-grid-selection-highlight..."
create_flag '{
  "key": "enable-grid-selection-highlight",
  "name": "Enable: grid selection highlight",
  "description": "When on, the selected grid cell shows a colored highlight in addition to the X marker. When off, evaluations receive none (X only, no color). Fallthrough chooses the base color; enable-grid-highlight-color-override can replace that with cohort colors from the login name.",
  "temporary": false,
  "tags": ["grid-navigator", "enable", "ui", "string"],
  "variations": [
    {
      "value": "none",
      "name": "No highlight",
      "description": "X only — no colors (matches 00-reference-code)"
    },
    {
      "value": "green",
      "name": "Green",
      "description": "Green selection highlight"
    },
    {
      "value": "yellow",
      "name": "Yellow",
      "description": "Yellow selection highlight"
    },
    {
      "value": "red",
      "name": "Red",
      "description": "Red selection highlight"
    },
    {
      "value": "blue",
      "name": "Blue",
      "description": "Blue selection highlight"
    },
    {
      "value": "purple",
      "name": "Purple",
      "description": "Purple selection highlight"
    }
  ],
  "defaults": {
    "onVariation": 1,
    "offVariation": 0
  }
}' | jq '{key, name, tags, temporary}'

echo "Creating enable-grid-highlight-color-override..."
create_flag '{
  "key": "enable-grid-highlight-color-override",
  "name": "Enable: grid highlight color override",
  "description": "When on (and enable-grid-selection-highlight serves a color), selection and username colors follow cohort rules parsed from the login name (human, robot, beta). When off, highlight uses the base fallthrough color from enable-grid-selection-highlight.",
  "temporary": false,
  "tags": ["grid-navigator", "enable", "ui", "context", "override"],
  "variations": [
    {
      "value": true,
      "name": "Override on",
      "description": "Apply cohort-based highlight and username colors from login name"
    },
    {
      "value": false,
      "name": "Override off",
      "description": "Use the base fallthrough color from enable-grid-selection-highlight"
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

echo "Creating show-host-os-emoji..."
create_flag '{
  "key": "show-host-os-emoji",
  "name": "Show: host OS emoji",
  "description": "When enabled, displays an OS emoji before the username. The host OS is sent as a private context attribute (hostOs) for targeting.",
  "temporary": true,
  "tags": ["grid-navigator", "show", "header", "private-attributes"],
  "variations": [
    {
      "value": true,
      "name": "Visible",
      "description": "Show OS emoji before username"
    },
    {
      "value": false,
      "name": "Hidden",
      "description": "No OS emoji (default)"
    }
  ],
  "defaults": {
    "onVariation": 0,
    "offVariation": 1
  }
}' | jq '{key, name, tags, temporary}'

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "Setting show-host-os-emoji to OFF in environment ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/show-host-os-emoji" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "{
      \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
      \"comment\": \"Default: no OS emoji\",
      \"instructions\": [{\"kind\": \"turnFlagOff\"}]
    }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"

  echo "Setting show-navigation-move-count to OFF in environment ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/show-navigation-move-count" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "{
      \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
      \"comment\": \"Default: navigation count hidden\",
      \"instructions\": [{\"kind\": \"turnFlagOff\"}]
    }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"

  echo "Setting enable-grid-highlight-color-override to OFF in environment ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/enable-grid-highlight-color-override" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "{
      \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
      \"comment\": \"Default: color override off (use base fallthrough color)\",
      \"instructions\": [{\"kind\": \"turnFlagOff\"}]
    }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"

  echo "Setting enable-grid-selection-highlight to OFF in environment ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/enable-grid-selection-highlight" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "{
      \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
      \"comment\": \"Default: X only, no colors\",
      \"instructions\": [{\"kind\": \"turnFlagOff\"}]
    }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"
fi

echo "Done."
