#!/usr/bin/env bash
# Create the six multitenant datacenter flags and the GDPR segment.
# The Flags tab writes targeting after this. It does not create the flags.
#
# Feature flags — variations
# https://launchdarkly.com/docs/home/flags/variations
# Feature flags — boolean variations
# https://launchdarkly.com/docs/home/flags/boolean
# Feature flags — segments
# https://launchdarkly.com/docs/home/flags/segments
# Feature flags — targeting rules
# https://launchdarkly.com/docs/home/flags/targeting-rules

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

TAG='["24-multitenant-datacenter"]'
SEGMENT="mtdc-gdpr-eu"

ensure_flag() {
  local key="$1"
  local body="$2"
  local existing created
  existing="$(api GET "/flags/${LD_PROJECT_KEY}/${key}")"
  if echo "${existing}" | jq -e '.key' >/dev/null 2>&1; then
    echo "  ${key}"
    return 0
  fi
  echo "  ${key} (creating)"
  created="$(api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d "${body}")"
  if ! echo "${created}" | jq -e '.key' >/dev/null 2>&1; then
    echo "${created}" >&2
    exit 1
  fi
  echo "${created}" | jq '{key, name, kind}'
}

ensure_gdpr_segment() {
  local existing rule_count created
  existing="$(api GET "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${SEGMENT}" || true)"
  if echo "${existing}" | jq -e '.key' >/dev/null 2>&1; then
    rule_count="$(echo "${existing}" | jq '.rules | length')"
    if [[ "${rule_count}" -gt 0 ]]; then
      echo "  ${SEGMENT}"
      return 0
    fi
    echo "  ${SEGMENT} (adding rule)"
    api PATCH "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${SEGMENT}" \
      -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
      -d "$(jq -n --arg env "${LD_ENVIRONMENT_KEY}" '{
        environmentKey: $env,
        comment: "24-multitenant-datacenter: gdpr true",
        instructions: [{
          kind: "addRule",
          description: "Datacenters with gdpr true",
          clauses: [{
            contextKind: "datacenter",
            attribute: "gdpr",
            op: "in",
            values: [true],
            negate: false
          }]
        }]
      }')" | jq '{key, rules: (.rules | length)}'
    return 0
  fi
  echo "  ${SEGMENT} (creating)"
  created="$(jq -n --argjson tags "${TAG}" '{
    key: "mtdc-gdpr-eu",
    name: "MTDC GDPR EU",
    description: "Datacenters with gdpr true. Data sharing and marketing serve false to this segment.",
    tags: $tags,
    rules: [{
      description: "Datacenters with gdpr true",
      clauses: [{
        contextKind: "datacenter",
        attribute: "gdpr",
        op: "in",
        values: [true],
        negate: false
      }]
    }]
  }' | api POST "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}" \
    -H "Content-Type: application/json" \
    -d @-)"
  if ! echo "${created}" | jq -e '.key' >/dev/null 2>&1; then
    echo "${created}" >&2
    exit 1
  fi
  echo "${created}" | jq '{key, name}'
}

# The first rule serves false to the GDPR segment. A later default-rule rollout cannot turn the EU on.
ensure_gdpr_rule() {
  local key="$1"
  local flag has false_id first_rule instructions
  flag="$(api GET "/flags/${LD_PROJECT_KEY}/${key}?env=${LD_ENVIRONMENT_KEY}")"
  has="$(echo "${flag}" | jq -r --arg env "${LD_ENVIRONMENT_KEY}" --arg seg "${SEGMENT}" '
    [(.environments[$env].rules // [])[] | .clauses[]? | select(.op == "segmentMatch") | .values[]? | select(. == $seg)] | length > 0
  ')"
  if [[ "${has}" == "true" ]]; then
    echo "  ${key} gdpr rule"
    return 0
  fi
  false_id="$(echo "${flag}" | jq -r '.variations[] | select(.value == false) | ._id')"
  if [[ -z "${false_id}" || "${false_id}" == "null" ]]; then
    echo "error: ${key} has no false variation" >&2
    exit 1
  fi
  first_rule="$(echo "${flag}" | jq -r --arg env "${LD_ENVIRONMENT_KEY}" '.environments[$env].rules[0]._id // empty')"
  echo "  ${key} gdpr rule (adding)"
  instructions="$(jq -n --arg id "${false_id}" --arg seg "${SEGMENT}" --arg before "${first_rule}" '
    {
      kind: "addRule",
      description: "GDPR EU stays off",
      variationId: $id,
      clauses: [{
        contextKind: "datacenter",
        attribute: "segmentMatch",
        op: "segmentMatch",
        values: [$seg],
        negate: false
      }]
    } + (if $before != "" then {beforeRuleId: $before} else {} end)
    | [.]
  ')"
  patched="$(api PATCH "/flags/${LD_PROJECT_KEY}/${key}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "$(jq -n --arg env "${LD_ENVIRONMENT_KEY}" --argjson instructions "${instructions}" '{
      environmentKey: $env,
      comment: "24-multitenant-datacenter: gdpr segment serves false",
      instructions: $instructions
    }')")"
  if ! echo "${patched}" | jq -e '.key' >/dev/null 2>&1; then
    echo "${patched}" >&2
    exit 1
  fi
  echo "  ${key} gdpr rule"
}

boolean_body() {
  local key="$1"
  local name="$2"
  local description="$3"
  jq -n --argjson tags "${TAG}" --arg key "${key}" --arg name "${name}" --arg description "${description}" '{
    key: $key,
    name: $name,
    description: $description,
    temporary: true,
    tags: $tags,
    variations: [
      {value: true, name: "On"},
      {value: false, name: "Off"}
    ],
    defaults: {onVariation: 1, offVariation: 1}
  }'
}

echo "Flags in ${LD_PROJECT_KEY}..."
ensure_flag "mtdc-border-palette" "$(jq -n --argjson tags "${TAG}" '{
  key: "mtdc-border-palette",
  name: "MTDC border palette",
  description: "String flag on the datacenter context. The palette is the border. Off serves none.",
  temporary: true,
  tags: $tags,
  variations: [
    {value: "none", name: "None"},
    {value: "roygbiv", name: "ROYGBIV"},
    {value: "contrast", name: "Contrast"},
    {value: "earth", name: "Earth"},
    {value: "ocean", name: "Ocean"},
    {value: "color-vision-aware", name: "Color-vision aware"}
  ],
  defaults: {onVariation: 0, offVariation: 0}
}')"

ensure_flag "mtdc-service-fill" "$(boolean_body \
  mtdc-service-fill \
  "MTDC service fill" \
  "Boolean flag on the service context. On fills the replica. Off leaves it empty. Fill does not change the version.")"

ensure_flag "mtdc-security" "$(boolean_body \
  mtdc-security \
  "MTDC security" \
  "Boolean flag on the customer context. A row matches when its size and its datacenter are both targeted. On turns the lock gold.")"

ensure_flag "mtdc-firewall" "$(boolean_body \
  mtdc-firewall \
  "MTDC firewall" \
  "Boolean flag on the customer context. Same size and datacenter targeting as security. On turns the wall teal. With security, the version becomes .2.")"

ensure_flag "mtdc-data-sharing" "$(boolean_body \
  mtdc-data-sharing \
  "MTDC data sharing" \
  "Boolean flag on the customer context. The first rule serves false to segment mtdc-gdpr-eu, so an EU datacenter stays off.")"

ensure_flag "mtdc-marketing" "$(boolean_body \
  mtdc-marketing \
  "MTDC marketing" \
  "Boolean flag on the customer context. The first rule serves false to segment mtdc-gdpr-eu. Marketing does not change the version.")"

echo "Segment in ${LD_PROJECT_KEY} / ${LD_ENVIRONMENT_KEY}..."
ensure_gdpr_segment
ensure_gdpr_rule "mtdc-data-sharing"
ensure_gdpr_rule "mtdc-marketing"

echo "Done. New flags are created off, and boolean fallthrough is false, so an on flag with no matching rule serves off. An existing flag is left as it is."
