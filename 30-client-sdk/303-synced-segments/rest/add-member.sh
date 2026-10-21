#!/usr/bin/env bash
# Add a user context key to marcoly-inner-circle (big-segment users POST, else semantic patch).
# https://launchdarkly.com/docs/api/segments/update-big-segment-targets
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

KEY="${1:-}"
if [[ -z "$KEY" ]]; then
  echo "usage: $0 <context-key>" >&2
  echo "example: $0 alice" >&2
  exit 1
fi

SEGMENT_KEY="marcoly-inner-circle"
ENV_PATH="/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${SEGMENT_KEY}"

echo "Adding '${KEY}' to ${SEGMENT_KEY}..."
http="$(
  curl -sS -X POST "${LD_API_HOST}/api/v2${ENV_PATH}/users" \
    -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
    -H "LD-API-Version: ${LD_API_VERSION}" \
    -H "Content-Type: application/json" \
    -o /tmp/ld-seg-out.json -w "%{http_code}" \
    -d "$(jq -nc --arg k "$KEY" '{included: {add: [$k]}}')"
)"
if [[ "$http" -ge 200 && "$http" -lt 300 ]]; then
  echo "OK (big-segment users POST, HTTP ${http})"
  exit 0
fi

echo "Big-segment POST HTTP ${http}; trying list-based addIncludedTargets..."
api PATCH "${ENV_PATH}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -nc --arg k "$KEY" '{
    comment: "33-synced-segments add member",
    instructions: [{kind: "addIncludedTargets", contextKind: "user", values: [$k]}]
  }')" | jq '{key, name}'

echo "Done."
