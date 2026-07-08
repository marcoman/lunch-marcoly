#!/usr/bin/env bash
# Show progressive-rollout state for the flag in the target environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

flag_json="$(fetch_flag)"
env_json="$(echo "${flag_json}" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\"")"
green_idx="$(echo "${flag_json}" | jq -r --arg color "${ROLLOUT_COLOR}" '.variations | to_entries[] | select(.value.value == $color) | .key' | head -1)"

echo "Flag: ${FLAG_KEY}"
echo "Environment: ${LD_ENVIRONMENT_KEY}"
echo "${env_json}" | jq '{
  on,
  offVariation,
  fallthrough,
  allocationType: (.fallthrough.rollout.experimentAllocation.type // null),
  progressiveRolloutConfig: (.fallthrough.progressiveRolloutConfig // null)
}'

summary="$(echo "${env_json}" | jq -r --argjson green_idx "${green_idx:-4}" '
  def green_pct(tracked):
    (.fallthrough.rollout.variations // [])
    | if tracked then map(select(._untracked != true)) else . end
    | map(select(.variation == $green_idx))
    | (map(.weight) | add // 0) / 1000;
  if .fallthrough.rollout.experimentAllocation.type == "measuredRollout" then
    "guarded:" + (green_pct(true) | tostring)
  elif .fallthrough.rollout.experimentAllocation.type == "progressiveRollout" then
    "progressive:" + (green_pct(true) | tostring)
  elif .fallthrough.progressiveRolloutConfig != null then
    "progressive-configured"
  elif .on == true and .fallthrough.rollout != null then
  "percentage:" + (green_pct(false) | tostring)
  elif .on == true and .fallthrough.variation != null then
    "fixed-variation"
  elif .on == true then
    "unknown-on"
  else
    "off"
  end
')"

echo
case "${summary}" in
  guarded:*)
    green="${summary#guarded:}"
    echo "Guarded rollout detected (measuredRollout, ${green}% green)."
    echo "This is not a progressive rollout — use 15-guarded-rollout instead."
    ;;
  progressive:*)
    green="${summary#progressive:}"
    echo "Active progressive rollout detected (progressiveRollout, ${green}% green)."
    ;;
  progressive-configured)
    echo "Progressive rollout configured on fallthrough (progressiveRolloutConfig present)."
    ;;
  percentage:*)
    green="${summary#percentage:}"
    echo "Percentage rollout via REST (${green}% green) — simulates progressive stages."
    echo "LaunchDarkly does not auto-advance this; use start-progressive-rollout.sh or configure in the UI."
    ;;
  fixed-variation)
    echo "Flag is on with fixed variation — no rollout."
    ;;
  off)
    echo "Flag is off."
    ;;
  *)
    echo "Flag state: ${summary}"
    ;;
esac
