#!/usr/bin/env bash
# Create enable-mobile-platform-rollout in state 1: platform in [android] serves true.
# Targeting rules: https://launchdarkly.com/docs/home/flags/target-with-rules
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

FLAG_KEY="enable-mobile-platform-rollout"
project="$(jq -nr --arg v "$LD_PROJECT_KEY" '$v|@uri')"
flag="$(jq -nr --arg v "$FLAG_KEY" '$v|@uri')"
environment="$(jq -nr --arg v "$LD_ENVIRONMENT_KEY" '$v|@uri')"

http="$(api_status GET "/flags/${project}/${flag}?env=${environment}")"
case "$http" in
  200)
    flag_json="$(api_ok GET "/flags/${project}/${flag}?env=${environment}")"
    if ! jq -e '([.variations[].value] | sort) == [false, true]' >/dev/null <<<"$flag_json"; then
      echo "error: existing ${FLAG_KEY} does not have exactly false/true variations" >&2
      exit 1
    fi
    if ! jq -e '.clientSideAvailability.usingMobileKey == true' >/dev/null <<<"$flag_json"; then
      echo "Enabling mobile-key availability on existing ${FLAG_KEY}..."
      api_ok PATCH "/flags/${project}/${flag}" \
        -H "Content-Type: application/json" \
        -d '[{"op":"replace","path":"/clientSideAvailability/usingMobileKey","value":true}]' >/dev/null
      flag_json="$(api_ok GET "/flags/${project}/${flag}?env=${environment}")"
    fi
    ;;
  404)
    echo "Creating ${FLAG_KEY}..."
    api_ok POST "/flags/${project}" \
      -H "Content-Type: application/json" \
      -d "$(jq -nc '{
        key: "enable-mobile-platform-rollout",
        name: "Enable: mobile platform rollout",
        description: "Boolean release flag. True is the new experience. Targeting starts with platform android.",
        temporary: true,
        tags: ["grid-navigator", "mobile-sdk", "platform-rollout"],
        clientSideAvailability: {usingEnvironmentId: true, usingMobileKey: true},
        variations: [
          {value: true, name: "New release", description: "Green cell and Release: on"},
          {value: false, name: "Previous", description: "Plain X and Release: waiting"}
        ],
        defaults: {onVariation: 0, offVariation: 1}
      }')" >/dev/null
    flag_json="$(api_ok GET "/flags/${project}/${flag}?env=${environment}")"
    ;;
  *)
    echo "error: unable to inspect ${FLAG_KEY} (HTTP ${http})" >&2
    exit 1
    ;;
esac

true_id="$(jq -er '.variations[] | select(.value == true) | ._id' <<<"$flag_json")"
false_id="$(jq -er '.variations[] | select(.value == false) | ._id' <<<"$flag_json")"
has_clause="$(jq -e --arg env "$LD_ENVIRONMENT_KEY" '
  [.environments[$env].rules[]?.clauses[]?
    | select(.attribute == "platform" and .op == "in")] | length > 0
' <<<"$flag_json")" || has_clause=""

if [[ -n "$has_clause" ]]; then
  patch="$(jq -nc \
    --arg environmentKey "$LD_ENVIRONMENT_KEY" \
    --arg previous "$false_id" '{
      environmentKey: $environmentKey,
      comment: "54-platform-rollout: keep the existing platform clause",
      instructions: [
        {kind: "updateOffVariation", variationId: $previous},
        {kind: "updateFallthroughVariationOrRollout", variationId: $previous},
        {kind: "turnFlagOn"}
      ]
    }')"
  echo "Platform clause already exists. Leaving its values alone."
else
  patch="$(jq -nc \
    --arg environmentKey "$LD_ENVIRONMENT_KEY" \
    --arg previous "$false_id" \
    --arg released "$true_id" '{
      environmentKey: $environmentKey,
      comment: "54-platform-rollout state 1: android serves the new release",
      instructions: [
        {kind: "updateOffVariation", variationId: $previous},
        {kind: "updateFallthroughVariationOrRollout", variationId: $previous},
        {kind: "addRule", description: "Android first", variationId: $released,
          clauses: [{contextKind: "user", attribute: "platform", op: "in", negate: false, values: ["android"]}]},
        {kind: "turnFlagOn"}
      ]
    }')"
  echo "Adding the android-only rule."
fi

api_ok PATCH "/flags/${project}/${flag}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$patch" >/dev/null

echo "Configured ${FLAG_KEY} in ${LD_ENVIRONMENT_KEY}. Run ./status.sh to see the platform values."
