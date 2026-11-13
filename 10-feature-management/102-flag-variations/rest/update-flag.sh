#!/usr/bin/env bash
# LaunchDarkly capability: REST API — update feature flag
# Demonstrates JSON Patch (flag metadata) and semantic patch (environment targeting).
# See: https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

FLAG_KEY="${1:-}"
if [[ -z "$FLAG_KEY" ]]; then
  echo "usage: $0 <flag-key>" >&2
  echo "example: $0 show-navigation-move-count" >&2
  exit 1
fi

if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "error: LD_ENVIRONMENT_KEY is required for the semantic patch example" >&2
  exit 1
fi

echo "Updating description via JSON Patch..."
api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "op": "replace",
      "path": "/description",
      "value": "Updated via REST API example — show navigation move count in grid header."
    }
  ]' | jq '{key, name, description}'

echo "Turning flag ON in environment ${LD_ENVIRONMENT_KEY} via semantic patch..."
api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "{
    \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
    \"comment\": \"Enable flag for testing\",
    \"instructions\": [{\"kind\": \"turnFlagOn\"}]
  }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"

echo "Done."
