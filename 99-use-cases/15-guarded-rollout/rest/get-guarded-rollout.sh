#!/usr/bin/env bash
# Show guarded-rollout state for the flag in the target environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

flag_json="$(fetch_flag_with_guarded_rollout)"
env_json="$(echo "${flag_json}" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\"")"
green_idx="$(echo "${flag_json}" | jq -r --arg color "${ROLLOUT_COLOR}" '.variations | to_entries[] | select(.value.value == $color) | .key' | head -1)"

echo "Flag: ${FLAG_KEY}"
echo "Environment: ${LD_ENVIRONMENT_KEY}"
echo "${env_json}" | jq '{
  on,
  offVariation,
  fallthrough,
  measuredRolloutType: (.fallthrough.rollout.experimentAllocation.type // null),
  guardedRolloutConfig: (.fallthrough.guardedRolloutConfig // null),
  guardedRollout: (.guardedRollout // null)
}'

summary="$(echo "${env_json}" | jq -r --argjson green_idx "${green_idx:-4}" '
  def green_pct:
    (.fallthrough.rollout.variations // [])
    | map(select(._untracked != true))
    | map(select(.variation == $green_idx))
    | (map(.weight) | add // 0) / 1000;
  if .guardedRollout != null then
    "guarded-expand"
  elif .fallthrough.guardedRolloutConfig != null then
    "guarded-config"
  elif .fallthrough.rollout.experimentAllocation.type == "measuredRollout" then
    "measured-rollout:" + (green_pct | tostring)
  elif .on == true then
    if .fallthrough.variation != null then "fixed-variation"
    elif .fallthrough.rollout != null then "percentage-rollout"
    else "unknown-on"
    end
  else
    "off"
  end
')"

echo
case "${summary}" in
  guarded-expand)
    echo "Active guarded rollout detected (expand=guardedRollout)."
    ;;
  guarded-config)
    echo "Guarded rollout configured on fallthrough (guardedRolloutConfig present)."
    ;;
  measured-rollout:*)
    green="${summary#measured-rollout:}"
    echo "Active guarded rollout detected (fallthrough measuredRollout, ${green}% green)."
    ;;
  fixed-variation)
    echo "Flag is on with fixed variation — not an active guarded rollout."
    echo "Configure Default rule → Guarded rollout in the UI, or run ./configure-guarded-rollout.sh."
    ;;
  percentage-rollout)
    echo "Flag is on with percentage rollout — not a guarded rollout."
    ;;
  off)
    echo "Flag is off."
    ;;
  *)
    echo "Flag state: ${summary}"
    ;;
esac
