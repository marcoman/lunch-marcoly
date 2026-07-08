#!/usr/bin/env bash
# Set the fallthrough percentage rollout: green vs none.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

PCT="${1:-}"
if [[ -z "${PCT}" ]] || ! [[ "${PCT}" =~ ^[0-9]+$ ]] || (( PCT < 0 || PCT > 100 )); then
  echo "usage: $0 <green-percent-0-100>" >&2
  exit 1
fi

flag_json="$(fetch_flag)"
green_id="$(variation_id "${flag_json}" "green")"
none_id="$(variation_id "${flag_json}" "none")"

if (( PCT == 0 )); then
  echo "Turning ${FLAG_KEY} OFF in ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "$(jq -n \
      --arg env "${LD_ENVIRONMENT_KEY}" \
      '{
        environmentKey: $env,
        comment: "Guarded rollout: turn flag off",
        instructions: [{kind: "turnFlagOff"}]
      }')" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough}"
  echo "Done."
  exit 0
fi

if (( PCT == 100 )); then
  echo "Setting ${FLAG_KEY} to 100% green in ${LD_ENVIRONMENT_KEY}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "$(jq -n \
      --arg env "${LD_ENVIRONMENT_KEY}" \
      --arg vid "${green_id}" \
      '{
        environmentKey: $env,
        comment: "Guarded rollout: 100% green",
        instructions: [
          {kind: "turnFlagOn"},
          {kind: "updateFallthroughVariationOrRollout", variationId: $vid}
        ]
      }')" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough}"
  echo "Done."
  exit 0
fi

none_pct=$((100 - PCT))
green_weight=$((PCT * 1000))
none_weight=$((none_pct * 1000))

echo "Setting ${FLAG_KEY} rollout in ${LD_ENVIRONMENT_KEY}: ${PCT}% green, ${none_pct}% none..."
api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg env "${LD_ENVIRONMENT_KEY}" \
    --arg green "${green_id}" \
    --arg none "${none_id}" \
    --argjson gw "${green_weight}" \
    --argjson nw "${none_weight}" \
    '{
      environmentKey: $env,
      comment: ("Guarded rollout: " + ($gw / 1000 | tostring) + "% green"),
      instructions: [
        {kind: "turnFlagOn"},
        {
          kind: "updateFallthroughVariationOrRollout",
          rolloutContextKind: "user",
          rolloutWeights: {($green): $gw, ($none): $nw}
        }
      ]
    }')" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, fallthrough}"

echo "Done."
