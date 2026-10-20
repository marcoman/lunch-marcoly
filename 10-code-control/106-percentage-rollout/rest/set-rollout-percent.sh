#!/usr/bin/env bash
# Set a static green/none percentage rollout on the default rule.
# This is plain percentage bucketing, not a progressive rollout schedule.
# https://launchdarkly.com/docs/home/flags/rollouts
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_environment

PCT="${1:-}"
if [[ -z "$PCT" ]] || ! [[ "$PCT" =~ ^[0-9]+$ ]] || ((PCT < 0 || PCT > 100)); then
  echo "usage: $0 <green-percent-0-100>" >&2
  exit 1
fi

flag_json="$(fetch_flag)"
green_id="$(variation_id "$flag_json" "green")"
none_id="$(variation_id "$flag_json" "none")"
green_weight=$((PCT * 1000))
none_weight=$(((100 - PCT) * 1000))

echo "Setting ${FLAG_KEY}: ${PCT}% green / $((100 - PCT))% none (bucket by user key)..."
api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$(jq -n \
    --arg env "$LD_ENVIRONMENT_KEY" \
    --arg green "$green_id" \
    --arg none "$none_id" \
    --argjson green_weight "$green_weight" \
    --argjson none_weight "$none_weight" \
    --arg pct "$PCT" \
    '{
      environmentKey: $env,
      comment: ("16-percentage-rollout: static " + $pct + "% green"),
      instructions: [
        {kind: "turnFlagOn"},
        {kind: "updateOffVariation", variationId: $none},
        {
          kind: "updateFallthroughVariationOrRollout",
          rolloutContextKind: "user",
          rolloutWeights: {($green): $green_weight, ($none): $none_weight}
        }
      ]
    }')" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on,offVariation,fallthrough}"
