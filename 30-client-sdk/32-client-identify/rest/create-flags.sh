#!/usr/bin/env bash
# LaunchDarkly capability: REST API — create client-side flags + key targeting
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag
# https://launchdarkly.com/docs/home/flags/target-rules
# Keywords: identify, targeting rules, client-side availability, context key

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

echo "Creating enable-identify-grid-highlight..."
create_flag '{
  "key": "enable-identify-grid-highlight",
  "name": "Enable: identify grid highlight",
  "description": "Browser string flag. Targeting on context key: alice→green, bob→blue, else none. For identify() demos.",
  "temporary": false,
  "tags": ["grid-navigator", "client-sdk", "identify", "enable", "ui", "string"],
  "clientSideAvailability": {
    "usingEnvironmentId": true,
    "usingMobileKey": false
  },
  "variations": [
    { "value": "none", "name": "No highlight", "description": "X only" },
    { "value": "green", "name": "Green", "description": "Alice" },
    { "value": "yellow", "name": "Yellow", "description": "Yellow" },
    { "value": "red", "name": "Red", "description": "Red" },
    { "value": "blue", "name": "Blue", "description": "Bob" },
    { "value": "purple", "name": "Purple", "description": "Purple" }
  ],
  "defaults": { "onVariation": 0, "offVariation": 0 }
}' | jq '{key, name, tags, clientSideAvailability}'

echo "Creating show-identify-move-count..."
create_flag '{
  "key": "show-identify-move-count",
  "name": "Show: identify move count",
  "description": "Browser boolean flag. Targeting on context key: alice→true, bob and fallthrough→false.",
  "temporary": true,
  "tags": ["grid-navigator", "client-sdk", "identify", "show", "header"],
  "clientSideAvailability": {
    "usingEnvironmentId": true,
    "usingMobileKey": false
  },
  "variations": [
    { "value": true, "name": "Visible", "description": "Alice sees Count" },
    { "value": false, "name": "Hidden", "description": "Bob / fallthrough hide Count" }
  ],
  "defaults": { "onVariation": 1, "offVariation": 1 }
}' | jq '{key, name, tags, clientSideAvailability}'

if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "LD_ENVIRONMENT_KEY not set; skipped targeting rules."
  echo "Done."
  exit 0
fi

echo "Adding alice/bob key rules in ${LD_ENVIRONMENT_KEY}..."

hl="$(api GET "/flags/${LD_PROJECT_KEY}/enable-identify-grid-highlight?env=${LD_ENVIRONMENT_KEY}")"
hl_none="$(jq -r '.variations[] | select(.value == "none") | ._id' <<<"$hl")"
hl_green="$(jq -r '.variations[] | select(.value == "green") | ._id' <<<"$hl")"
hl_blue="$(jq -r '.variations[] | select(.value == "blue") | ._id' <<<"$hl")"

cnt="$(api GET "/flags/${LD_PROJECT_KEY}/show-identify-move-count?env=${LD_ENVIRONMENT_KEY}")"
cnt_true="$(jq -r '.variations[] | select(.value == true) | ._id' <<<"$cnt")"
cnt_false="$(jq -r '.variations[] | select(.value == false) | ._id' <<<"$cnt")"

hl_patch="$(jq -n \
  --arg env "$LD_ENVIRONMENT_KEY" \
  --arg none "$hl_none" --arg green "$hl_green" --arg blue "$hl_blue" \
  '{
    environmentKey: $env,
    comment: "32-client-identify: alice/bob key rules",
    instructions: [
      {kind: "turnFlagOn"},
      {kind: "updateOffVariation", variationId: $none},
      {kind: "updateFallthroughVariationOrRollout", variationId: $none},
      {kind: "addRule", description: "Alice", clauses: [{contextKind:"user", attribute:"key", op:"in", values:["alice"], negate:false}], variationId:$green},
      {kind: "addRule", description: "Bob", clauses: [{contextKind:"user", attribute:"key", op:"in", values:["bob"], negate:false}], variationId:$blue}
    ]
  }')"
api PATCH "/flags/${LD_PROJECT_KEY}/enable-identify-grid-highlight" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$hl_patch" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough, rules: [.rules[]? | {description}]}"

cnt_patch="$(jq -n \
  --arg env "$LD_ENVIRONMENT_KEY" \
  --arg vis "$cnt_true" --arg hid "$cnt_false" \
  '{
    environmentKey: $env,
    comment: "32-client-identify: alice/bob key rules",
    instructions: [
      {kind: "turnFlagOn"},
      {kind: "updateOffVariation", variationId: $hid},
      {kind: "updateFallthroughVariationOrRollout", variationId: $hid},
      {kind: "addRule", description: "Alice", clauses: [{contextKind:"user", attribute:"key", op:"in", values:["alice"], negate:false}], variationId:$vis},
      {kind: "addRule", description: "Bob", clauses: [{contextKind:"user", attribute:"key", op:"in", values:["bob"], negate:false}], variationId:$hid}
    ]
  }')"
api PATCH "/flags/${LD_PROJECT_KEY}/show-identify-move-count" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$cnt_patch" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough, rules: [.rules[]? | {description}]}"

echo "Done."
