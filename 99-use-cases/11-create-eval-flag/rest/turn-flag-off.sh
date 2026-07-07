#!/usr/bin/env bash
# Turn the highlight flag OFF (every user gets the off variation: none).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

echo "Turning ${FLAG_KEY} OFF in ${LD_ENVIRONMENT_KEY}..."
api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "{
    \"environmentKey\": \"${LD_ENVIRONMENT_KEY}\",
    \"comment\": \"Create/eval: turn flag off\",
    \"instructions\": [{\"kind\": \"turnFlagOff\"}]
  }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough}"

echo "Done."
