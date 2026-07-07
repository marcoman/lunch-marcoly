#!/usr/bin/env bash
# Change fallthrough highlight color while the flag is ON.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

COLOR="${1:-}"
if [[ -z "${COLOR}" ]]; then
  echo "usage: $0 <green|yellow|red|blue|purple>" >&2
  exit 1
fi

flag_json="$(fetch_flag)"
vid="$(variation_id "${flag_json}" "${COLOR}")"
if [[ -z "${vid}" ]]; then
  echo "error: variation \"${COLOR}\" not found on flag" >&2
  exit 1
fi

echo "Setting fallthrough to ${COLOR} in ${LD_ENVIRONMENT_KEY}..."
api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg env "${LD_ENVIRONMENT_KEY}" \
    --arg vid "${vid}" \
    '{
      environmentKey: $env,
      comment: "Create/eval: change highlight color",
      instructions: [
        {kind: "updateFallthroughVariationOrRollout", variationId: $vid}
      ]
    }')" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough, offVariation}"

echo "Done."
