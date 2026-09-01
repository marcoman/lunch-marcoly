#!/usr/bin/env bash
# Create show-partner-org-badge with two AND multi-context targeting rules.
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag
# https://launchdarkly.com/docs/home/flags/multi-contexts
# Keywords: multi-context, targeting rules, context kinds
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

FLAG_KEY="show-partner-org-badge"

echo "Creating ${FLAG_KEY}..."
flag_status="$(api_status GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}")"
if [[ "$flag_status" == "200" ]]; then
  echo "Flag already exists."
else
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
      "key": "show-partner-org-badge",
      "name": "Show: partner org badge",
      "description": "True for alice+acme and bob+globex via user+organization multi-context rules.",
      "temporary": true,
      "tags": ["grid-navigator", "show", "multi-context", "targeting"],
      "variations": [
        {"value": true, "name": "Badge on", "description": "Show partner badge"},
        {"value": false, "name": "Badge off", "description": "No badge"}
      ],
      "defaults": {"onVariation": 0, "offVariation": 1}
    }' | jq '{key,name,tags,variations:[.variations[]|{value,name}]}'
fi

if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "LD_ENVIRONMENT_KEY not set; skipped targeting."
  echo "Done."
  exit 0
fi

echo "Reading variation IDs..."
flag_json="$(api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}?env=${LD_ENVIRONMENT_KEY}")"
true_id="$(jq -r '.variations[] | select(.value == true) | ._id' <<<"$flag_json")"
false_id="$(jq -r '.variations[] | select(.value == false) | ._id' <<<"$flag_json")"

has_alice="$(jq --arg env "$LD_ENVIRONMENT_KEY" '
  (.environments[$env].rules // [])
  | map(.clauses)
  | map(select(
      (map(select(.contextKind == "user" and .attribute == "key" and (.values|index("alice")))) | length > 0)
      and
      (map(select(.contextKind == "organization" and .attribute == "key" and (.values|index("acme")))) | length > 0)
    ))
  | length > 0
' <<<"$flag_json")"

if [[ "$has_alice" == "true" ]]; then
  echo "Turning flag ON (rules already present) in ${LD_ENVIRONMENT_KEY}..."
  patch="$(jq -n --arg env "$LD_ENVIRONMENT_KEY" --arg hid "$false_id" '{
    environmentKey: $env,
    comment: "14-multi-context-targeting: flag on (rules already present)",
    instructions: [
      {kind: "turnFlagOn"},
      {kind: "updateOffVariation", variationId: $hid},
      {kind: "updateFallthroughVariationOrRollout", variationId: $hid}
    ]
  }')"
else
  echo "Turning flag ON and adding alice+acme / bob+globex rules in ${LD_ENVIRONMENT_KEY}..."
  patch="$(jq -n \
    --arg env "$LD_ENVIRONMENT_KEY" \
    --arg vis "$true_id" --arg hid "$false_id" \
    '{
      environmentKey: $env,
      comment: "14-multi-context-targeting: user+organization AND rules",
      instructions: [
        {kind: "turnFlagOn"},
        {kind: "updateOffVariation", variationId: $hid},
        {kind: "updateFallthroughVariationOrRollout", variationId: $hid},
        {
          kind: "addRule",
          description: "Alice at Acme",
          clauses: [
            {contextKind: "user", attribute: "key", op: "in", values: ["alice"], negate: false},
            {contextKind: "organization", attribute: "key", op: "in", values: ["acme"], negate: false}
          ],
          variationId: $vis
        },
        {
          kind: "addRule",
          description: "Bob at Globex",
          clauses: [
            {contextKind: "user", attribute: "key", op: "in", values: ["bob"], negate: false},
            {contextKind: "organization", attribute: "key", op: "in", values: ["globex"], negate: false}
          ],
          variationId: $vis
        }
      ]
    }')"
fi

api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$patch" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough, rules: [.rules[]? | {description, clauses: [.clauses[] | {contextKind, attribute, values}]}]}"

echo "Done."
