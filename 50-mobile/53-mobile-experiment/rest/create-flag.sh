#!/usr/bin/env bash
# Create the boolean experiment flag and safely configure one environment.
# Feature flags — boolean variations and mobile SDK availability:
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

FLAG_KEY="acme-mobile-onboarding-v2"
project="$(urlencode "$LD_PROJECT_KEY")"
flag="$(urlencode "$FLAG_KEY")"
environment="$(urlencode "$LD_ENVIRONMENT_KEY")"

api_request GET "/flags/${project}/${flag}?env=${environment}"
case "$API_HTTP_STATUS" in
  200)
    if ! jq -e '
      ([.variations[].value] | sort) == [false, true]
    ' >/dev/null <<<"$API_RESPONSE"; then
      echo "error: existing ${FLAG_KEY} does not have exactly false/true variations" >&2
      exit 1
    fi
    if ! jq -e '.clientSideAvailability.usingMobileKey == true' \
      >/dev/null <<<"$API_RESPONSE"; then
      echo "Enabling mobile-key availability on existing ${FLAG_KEY}..."
      api_ok PATCH "/flags/${project}/${flag}" \
        -H "Content-Type: application/json" \
        -d '[{
          "op": "replace",
          "path": "/clientSideAvailability/usingMobileKey",
          "value": true
        }]' >/dev/null
    else
      echo "Flag ${FLAG_KEY} already exists with mobile-key availability."
    fi
    ;;
  404)
    echo "Creating ${FLAG_KEY}..."
    api_ok POST "/flags/${project}" \
      -H "Content-Type: application/json" \
      -d "$(jq -nc '{
        key: "acme-mobile-onboarding-v2",
        name: "Acme: mobile onboarding helper",
        description: "Boolean experiment flag. False is control; true shows the onboarding helper.",
        temporary: true,
        tags: ["acme", "mobile-sdk", "experimentation", "onboarding"],
        clientSideAvailability: {
          usingEnvironmentId: true,
          usingMobileKey: true
        },
        variations: [
          {value: false, name: "Control", description: "Open the grid immediately"},
          {value: true, name: "Treatment", description: "Show How to play before the grid"}
        ],
        defaults: {onVariation: 1, offVariation: 0}
      }')" >/dev/null
    ;;
  *)
    echo "error: unable to inspect ${FLAG_KEY} (HTTP ${API_HTTP_STATUS})" >&2
    jq . <<<"$API_RESPONSE" 2>/dev/null || printf '%s\n' "$API_RESPONSE" >&2
    exit 1
    ;;
esac

# Variation IDs are server-generated, so read them before configuring targeting.
flag_json="$(api_ok GET "/flags/${project}/${flag}?env=${environment}")"
control_id="$(jq -er '.variations[] | select(.value == false) | ._id' <<<"$flag_json")"
treatment_id="$(jq -er '.variations[] | select(.value == true) | ._id' <<<"$flag_json")"
# Semantic patch avoids interpolating the environment into a JSON string.
# It establishes the safe state: off serves false; on fallthrough serves true.
patch="$(jq -nc \
  --arg environmentKey "$LD_ENVIRONMENT_KEY" \
  --arg control "$control_id" \
  --arg treatment "$treatment_id" '{
    environmentKey: $environmentKey,
    comment: "53-mobile-experiment: false off/control, true on/treatment",
    instructions: [
      {kind: "updateOffVariation", variationId: $control},
      {kind: "updateFallthroughVariationOrRollout", variationId: $treatment},
      {kind: "turnFlagOff"}
    ]
  }')"
api_ok PATCH "/flags/${project}/${flag}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$patch" >/dev/null

echo "Configured ${FLAG_KEY} in ${LD_ENVIRONMENT_KEY}: off=false, on fallthrough=true, currently OFF."
