#!/usr/bin/env bash
# Turn targeting off so evaluations return the off variation (none).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg environmentKey "${LD_ENVIRONMENT_KEY}" \
    '{
      environmentKey: $environmentKey,
      comment: "16-adaptive-triggers: stop targeting",
      instructions: [{kind: "turnFlagOff"}]
    }')" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough}"

echo "Stopped: ${FLAG_KEY} is off and serves ${SAFE_COLOR}. Remove the adaptive trigger in the UI if you want a clean slate."
