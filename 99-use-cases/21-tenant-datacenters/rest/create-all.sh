#!/usr/bin/env bash
# Create the border palette, the fill flag, and the tenant segments.
# Flag variations: https://launchdarkly.com/docs/home/flags/variations
# Boolean flags: https://launchdarkly.com/docs/home/flags/boolean
# Segments: https://launchdarkly.com/docs/home/flags/segments
# Keep the segment keys in step with ../flags.py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

TAG='["tenant-datacenters", "use-case"]'

ensure_flag() {
  local key="$1"
  local body="$2"
  local existing
  existing="$(api GET "/flags/${LD_PROJECT_KEY}/${key}")"
  if echo "${existing}" | jq -e '.key' >/dev/null 2>&1; then
    echo "  ${key}"
    return 0
  fi
  echo "  ${key} (creating)"
  api POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d "${body}" | jq '{key, name, kind}'
}

ensure_segment() {
  local key="$1"
  local name="$2"
  local attribute="$3"
  local values_json="$4"
  local existing rule_count patch_body
  existing="$(api GET "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${key}" || true)"
  if echo "${existing}" | jq -e '.key' >/dev/null 2>&1; then
    rule_count="$(echo "${existing}" | jq '.rules | length')"
    if [[ "${rule_count}" -gt 0 ]]; then
      echo "  ${key}"
      return 0
    fi
    echo "  ${key} (adding rule)"
    patch_body="$(jq -n \
      --arg env "${LD_ENVIRONMENT_KEY}" \
      --arg attr "${attribute}" \
      --argjson vals "${values_json}" \
      '{
        environmentKey: $env,
        comment: "Match the tenant context attribute",
        instructions: [{
          kind: "addRule",
          description: "Match the tenant context attribute",
          clauses: [{
            contextKind: "tenant",
            attribute: $attr,
            op: "in",
            values: $vals,
            negate: false
          }]
        }]
      }')"
    api PATCH "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${key}" \
      -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
      -d "${patch_body}" | jq '{key, rules: (.rules | length)}'
    return 0
  fi
  echo "  ${key} (creating)"
  jq -n \
    --arg key "${key}" \
    --arg name "${name}" \
    --arg attr "${attribute}" \
    --argjson tags "${TAG}" \
    --argjson vals "${values_json}" \
    '{
      key: $key,
      name: $name,
      tags: $tags,
      rules: [{
        clauses: [{
          contextKind: "tenant",
          attribute: $attr,
          op: "in",
          values: $vals,
          negate: false
        }]
      }]
    }' | api POST "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}" \
      -H "Content-Type: application/json" \
      -d @- | jq '{key, name}'
}

echo "Flags in ${LD_PROJECT_KEY}..."
ensure_flag "tenant-border-palette" "$(jq -n --argjson tags "${TAG}" '{
  key: "tenant-border-palette",
  name: "Tenant border palette",
  description: "One palette for every tenant border. none keeps the hairline. Size class picks the hue inside the palette.",
  temporary: false,
  tags: ($tags + ["multivariate"]),
  variations: [
    {value: "none", name: "None"},
    {value: "roygbiv", name: "ROYGBIV"},
    {value: "grays", name: "Grays"},
    {value: "earth", name: "Earth"},
    {value: "ocean", name: "Ocean"}
  ],
  defaults: {onVariation: 1, offVariation: 0}
}')"

ensure_flag "tenant-box-fill" "$(jq -n --argjson tags "${TAG}" '{
  key: "tenant-box-fill",
  name: "Tenant box fill",
  description: "Fill every tenant box with a translucent tint of its border hue. A fill with no palette paints nothing.",
  temporary: false,
  tags: ($tags + ["boolean"]),
  variations: [
    {value: true, name: "Fill"},
    {value: false, name: "Empty"}
  ],
  defaults: {onVariation: 0, offVariation: 1}
}')"

echo "Segments in ${LD_PROJECT_KEY} / ${LD_ENVIRONMENT_KEY}..."
ensure_segment tenant-size-small "Small tenants" sizeClass '["small"]'
ensure_segment tenant-size-medium "Medium tenants" sizeClass '["medium"]'
ensure_segment tenant-size-large "Large tenants" sizeClass '["large"]'
ensure_segment tenant-size-unknown "Unknown tenants" sizeClass '["unknown"]'
ensure_segment tenant-dc-01 "DC01" datacenter '["DC01"]'
ensure_segment tenant-dc-02 "DC02" datacenter '["DC02"]'
ensure_segment tenant-dc-03 "DC03" datacenter '["DC03"]'
ensure_segment tenant-dc-04 "DC04" datacenter '["DC04"]'
ensure_segment tenant-dc-05 "DC05" datacenter '["DC05"]'
ensure_segment tenant-footprint-single "Single-site tenants" span '[1]'
ensure_segment tenant-footprint-multi "Multi-site tenants" span '[2, 3, 5]'
ensure_segment tenant-footprint-all-five "Tenants in all five datacenters" span '[5]'

echo "Done. Both flags are off until targeting is turned on. The border flag's on variation is roygbiv."
