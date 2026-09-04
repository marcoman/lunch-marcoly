#!/usr/bin/env bash
# LaunchDarkly capability: REST API — JSON Patch + semantic patch
# (turnFlagOn / turnFlagOff)
# https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

FLAG_KEY="${1:-}"
ACTION="${2:-on}"
if [[ -z "$FLAG_KEY" ]]; then
  echo "usage: $0 <flag-key> [on|off]" >&2
  echo "example: $0 show-mobile-move-count on" >&2
  exit 1
fi

case "$ACTION" in
  on) kind="turnFlagOn" ;;
  off) kind="turnFlagOff" ;;
  *)
    echo "usage: $0 <flag-key> [on|off]" >&2
    exit 1
    ;;
esac

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
      "value": "Updated via REST API example — 52-mobile-evaluation."
    }
  ]' | jq '{key, name, description}'

echo "Turning flag ${ACTION} in environment ${LD_ENVIRONMENT_KEY} via semantic patch..."
api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "{
    \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
    \"comment\": \"Turn flag ${ACTION} for testing\",
    \"instructions\": [{\"kind\": \"${kind}\"}]
  }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"

echo "Done."
