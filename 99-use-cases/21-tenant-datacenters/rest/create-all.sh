#!/usr/bin/env bash
# Create the border palette, the fill flag, the security flag, the firewall
# flag, and the tenant segments.
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

sync_border_variations() {
  local flag grays_id contrast_id aware_id instructions
  flag="$(api GET "/flags/${LD_PROJECT_KEY}/tenant-border-palette")"
  grays_id="$(echo "${flag}" | jq -r '.variations[] | select(.value == "grays") | (._id // .id // empty)')"
  contrast_id="$(echo "${flag}" | jq -r '.variations[] | select(.value == "contrast") | (._id // .id // empty)')"
  aware_id="$(echo "${flag}" | jq -r '.variations[] | select(.value == "color-vision-aware") | (._id // .id // empty)')"
  instructions='[]'
  if [[ -n "${grays_id}" && -z "${contrast_id}" ]]; then
    instructions="$(echo "${instructions}" | jq --arg id "${grays_id}" '. + [{
      kind: "updateVariation",
      variationId: $id,
      value: "contrast",
      name: "Contrast",
      description: "Cyan, gold, magenta, and lime. The hues sit far apart."
    }]')"
  elif [[ -z "${contrast_id}" ]]; then
    instructions="$(echo "${instructions}" | jq '. + [{
      kind: "addVariation",
      value: "contrast",
      name: "Contrast",
      description: "Cyan, gold, magenta, and lime. The hues sit far apart."
    }]')"
  fi
  if [[ -z "${aware_id}" ]]; then
    instructions="$(echo "${instructions}" | jq '. + [{
      kind: "addVariation",
      value: "color-vision-aware",
      name: "Color-vision aware",
      description: "Okabe-Ito hues for common red-green color-vision deficiencies. This does not cover every type."
    }]')"
  fi
  if [[ "${instructions}" == "[]" ]]; then
    echo "  tenant-border-palette variations"
    return 0
  fi
  echo "  tenant-border-palette variations"
  api PATCH "/flags/${LD_PROJECT_KEY}/tenant-border-palette" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "$(jq -n --argjson instructions "${instructions}" '{comment: "21-tenant-datacenters: palette variations", instructions: $instructions}')" \
    | jq '{key, variations: [.variations[] | {value, name}]}'
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
    {value: "contrast", name: "Contrast"},
    {value: "earth", name: "Earth"},
    {value: "ocean", name: "Ocean"},
    {value: "color-vision-aware", name: "Color-vision aware", description: "Okabe-Ito hues for common red-green color-vision deficiencies. This does not cover every type."}
  ],
  defaults: {onVariation: 1, offVariation: 0}
}')"
sync_border_variations

ensure_flag "tenant-security" "$(jq -n --argjson tags "${TAG}" '{
  key: "tenant-security",
  name: "Tenant security",
  description: "Enable security, shown as a lock. By name, the lab targets S01, then the next name. By datacenter, the lab targets Large in DC01, then the next datacenter. Full deployment targets Small by size, then Medium from DC01 through DC05, then L01. Unknown stays off.",
  temporary: false,
  tags: ($tags + ["boolean"]),
  variations: [
    {value: true, name: "Enabled"},
    {value: false, name: "Off"}
  ],
  defaults: {onVariation: 0, offVariation: 1}
}')"

ensure_flag "tenant-firewall" "$(jq -n --argjson tags "${TAG}" '{
  key: "tenant-firewall",
  name: "Tenant firewall",
  description: "Draw a firewall icon. Off draws nothing. The manual release on this flag chooses who gets the icon.",
  temporary: false,
  tags: ($tags + ["boolean"]),
  variations: [
    {value: true, name: "Enabled"},
    {value: false, name: "Off"}
  ],
  defaults: {onVariation: 0, offVariation: 1}
}')"

FILL_URL="${LD_APP_HOST:-${LD_API_HOST:-https://app.launchdarkly.com}}"
FILL_URL="${FILL_URL%/}/projects/${LD_PROJECT_KEY}/flags/tenant-box-fill?env=${LD_ENVIRONMENT_KEY}&selected-env=${LD_ENVIRONMENT_KEY}"
FILL_DESCRIPTION="Fill every tenant box with a translucent tint of its border hue. A fill with no palette paints nothing. ${FILL_URL}"

ensure_flag "tenant-box-fill" "$(jq -n --argjson tags "${TAG}" --arg description "${FILL_DESCRIPTION}" '{
  key: "tenant-box-fill",
  name: "Tenant box fill",
  description: $description,
  temporary: false,
  tags: ($tags + ["boolean"]),
  variations: [
    {value: true, name: "Fill"},
    {value: false, name: "Empty"}
  ],
  defaults: {onVariation: 0, offVariation: 1}
}')"

echo "  tenant-box-fill description"
api PATCH "/flags/${LD_PROJECT_KEY}/tenant-box-fill" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg description "${FILL_DESCRIPTION}" '[{op: "replace", path: "/description", value: $description}]')" \
  | jq '{key, description}'

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

echo "Done. Flags stay off until targeting is turned on. The border flag's on variation is roygbiv."
