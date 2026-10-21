#!/usr/bin/env bash
# LaunchDarkly: create inner-circle segment + client-side boolean flag.
# https://launchdarkly.com/docs/api/segments/post-segment
# https://launchdarkly.com/docs/api/segments/update-big-segment-targets
# https://launchdarkly.com/docs/home/flags/synced-segments
# Keywords: synced segments, unbounded, segmentMatch, client-side availability

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

SEGMENT_KEY="marcoly-inner-circle"
FLAG_KEY="show-inner-circle-badge"

echo "Creating segment ${SEGMENT_KEY} (prefer unbounded / big)..."
seg_status="$(api_status GET "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${SEGMENT_KEY}")"
if [[ "$seg_status" == "200" ]]; then
  echo "Segment already exists."
else
  unbounded_body='{
    "name": "Marcoly inner circle",
    "key": "marcoly-inner-circle",
    "description": "Inner-circle membership. Lab injects keys via REST; production would sync from Twilio Segment Audiences.",
    "tags": ["grid-navigator", "client-sdk", "synced-segments"],
    "unbounded": true,
    "unboundedContextKind": "user"
  }'
  tmp="$(mktemp)"
  http="$(
    curl -sS -X POST "${LD_API_HOST}/api/v2/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}" \
      -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
      -H "LD-API-Version: ${LD_API_VERSION}" \
      -H "Content-Type: application/json" \
      -o "$tmp" -w "%{http_code}" \
      -d "$unbounded_body"
  )"
  if [[ "$http" -ge 200 && "$http" -lt 300 ]]; then
    echo "Created unbounded (big/synced-style) segment."
    jq '{key, name, unbounded}' "$tmp"
  else
    echo "Unbounded create failed (HTTP ${http}); falling back to a list-based segment."
    jq . "$tmp" 2>/dev/null || cat "$tmp"
    api POST "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}" \
      -H "Content-Type: application/json" \
      -d '{
        "name": "Marcoly inner circle",
        "key": "marcoly-inner-circle",
        "description": "List-based fallback: included user keys. Same flag rule as the unbounded path.",
        "tags": ["grid-navigator", "client-sdk", "synced-segments", "list-fallback"]
      }' | jq '{key, name, unbounded}'
  fi
  rm -f "$tmp"
fi

echo "Creating flag ${FLAG_KEY}..."
flag_status="$(api_status GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}")"
if [[ "$flag_status" == "200" ]]; then
  echo "Flag already exists."
else
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
      "key": "show-inner-circle-badge",
      "name": "Show: inner circle badge",
      "description": "True when the context is in marcoly-inner-circle. Client-side JS evaluation.",
      "temporary": false,
      "tags": ["grid-navigator", "client-sdk", "segments", "synced-segments", "show"],
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
    comment: "33-synced-segments: flag on (segment rule already present)",
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
      comment: "33-synced-segments: inner circle segment rule",
      instructions: [
        {kind: "turnFlagOn"},
        {kind: "updateOffVariation", variationId: $hid},
        {kind: "updateFallthroughVariationOrRollout", variationId: $hid},
        {
          kind: "addRule",
          description: "Inner circle",
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
