#!/usr/bin/env bash
# Create the move-count flag used by the approval lab. Leave it off.
# Do not patch targeting. An environment that requires approvals would turn
# that patch into another request.
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag
# Keywords: feature flags, boolean variations, approvals
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

status="$(api_status GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}")"
if [[ "$status" == "200" ]]; then
  echo "Flag already exists."
else
  echo "Creating ${FLAG_KEY}..."
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
      \"key\": \"${FLAG_KEY}\",
      \"name\": \"Show: navigation move count (approval)\",
      \"description\": \"108-flag-approvals. Cites 101 show-navigation-move-count. Dedicated key. Turn it on through an approval request, not a direct patch.\",
      \"temporary\": true,
      \"tags\": [\"grid-navigator\", \"show\", \"header\", \"approval\"],
      \"variations\": [
        {\"value\": true, \"name\": \"Visible\", \"description\": \"Display Count: N\"},
        {\"value\": false, \"name\": \"Hidden\", \"description\": \"Hide the count\"}
      ],
      \"defaults\": {\"onVariation\": 0, \"offVariation\": 1}
    }" | jq '{key, name, temporary}'
fi

if [[ -n "${LD_ENVIRONMENT_KEY:-}" ]]; then
  api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}?env=${LD_ENVIRONMENT_KEY}" \
    | jq --arg env "$LD_ENVIRONMENT_KEY" '.environments[$env] | {on}'
fi
