#!/usr/bin/env bash
# LaunchDarkly: create the Twilio-lab badge flag targeted at a synced segment.
# Does NOT create the segment — Twilio Segment Audiences does that on first sync.
# https://launchdarkly.com/docs/home/flags/twilio
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag
# Keywords: synced segments, Twilio Segment Audiences, segmentMatch, client-side availability

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

SEGMENT_KEY="${LD_TWILIO_SEGMENT_KEY:-marcoly-twilio-inner-circle}"
FLAG_KEY="show-twilio-inner-circle-badge"

echo "Looking up synced segment ${SEGMENT_KEY} (created by Twilio, not this script)..."
seg_status="$(api_status GET "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${SEGMENT_KEY}")"
if [[ "$seg_status" == "200" ]]; then
  echo "Segment found."
  api GET "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${SEGMENT_KEY}" | jq '{key, name, unbounded}'
else
  echo "WARNING: segment ${SEGMENT_KEY} HTTP ${seg_status}."
  echo "Create a Twilio Engage Audience, add the LaunchDarkly Audiences destination,"
  echo "wait for the first sync (~10 minutes), then copy the LaunchDarkly segment KEY"
  echo "into LD_TWILIO_SEGMENT_KEY and re-run this script so the flag rule matches."
  echo "Docs: https://launchdarkly.com/docs/home/flags/twilio"
fi

echo "Creating flag ${FLAG_KEY}..."
flag_status="$(api_status GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}")"
if [[ "$flag_status" == "200" ]]; then
  echo "Flag already exists."
else
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
      "key": "show-twilio-inner-circle-badge",
      "name": "Show: Twilio inner circle badge",
      "description": "True when the context is in the Twilio Segment–synced inner-circle audience. Client-side JS evaluation.",
      "temporary": false,
      "tags": ["grid-navigator", "client-sdk", "segments", "synced-segments", "twilio", "show"],
      "clientSideAvailability": {
        "usingEnvironmentId": true,
        "usingMobileKey": false
      },
      "variations": [
        { "value": true, "name": "Badge on", "description": "Show inner-circle badge" },
        { "value": false, "name": "Badge off", "description": "No badge" }
      ],
      "defaults": { "onVariation": 0, "offVariation": 1 }
    }' | jq '{key, name, tags, clientSideAvailability}'
fi

if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "LD_ENVIRONMENT_KEY not set; skipped targeting."
  echo "Done."
  exit 0
fi

echo "Turning flag ON with segmentMatch rule in ${LD_ENVIRONMENT_KEY}..."
flag_json="$(api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}?env=${LD_ENVIRONMENT_KEY}")"
true_id="$(jq -r '.variations[] | select(.value == true) | ._id' <<<"$flag_json")"
false_id="$(jq -r '.variations[] | select(.value == false) | ._id' <<<"$flag_json")"
has_rule="$(jq --arg env "$LD_ENVIRONMENT_KEY" --arg seg "$SEGMENT_KEY" '
  (.environments[$env].rules // [])
  | map(.clauses[]? | select(.op == "segmentMatch") | .values[]?)
  | index($seg) != null
' <<<"$flag_json")"

if [[ "$has_rule" == "true" ]]; then
  patch="$(jq -n --arg env "$LD_ENVIRONMENT_KEY" --arg hid "$false_id" '{
    environmentKey: $env,
    comment: "34-synced-segments-twilio: flag on (segment rule already present)",
    instructions: [
      {kind: "turnFlagOn"},
      {kind: "updateOffVariation", variationId: $hid},
      {kind: "updateFallthroughVariationOrRollout", variationId: $hid}
    ]
  }')"
else
  patch="$(jq -n \
    --arg env "$LD_ENVIRONMENT_KEY" \
    --arg vis "$true_id" --arg hid "$false_id" --arg seg "$SEGMENT_KEY" \
    '{
      environmentKey: $env,
      comment: "34-synced-segments-twilio: Twilio-synced segment rule",
      instructions: [
        {kind: "turnFlagOn"},
        {kind: "updateOffVariation", variationId: $hid},
        {kind: "updateFallthroughVariationOrRollout", variationId: $hid},
        {
          kind: "addRule",
          description: "Twilio inner circle",
          clauses: [{
            contextKind: "user",
            attribute: "",
            op: "segmentMatch",
            values: [$seg],
            negate: false
          }],
          variationId: $vis
        }
      ]
    }')"
fi
api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$patch" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough, rules: [.rules[]? | {description}]}"

echo "Done."
