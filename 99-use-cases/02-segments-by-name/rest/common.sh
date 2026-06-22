#!/usr/bin/env bash
# Shared REST helpers for 02-segments-by-name.

set -euo pipefail

: "${LD_API_HOST:=https://app.launchdarkly.com}"
: "${LD_API_VERSION:=20240415}"

if [[ -z "${LD_API_ACCESS_TOKEN:-}" ]]; then
  echo "error: LD_API_ACCESS_TOKEN is required" >&2
  exit 1
fi

if [[ -z "${LD_PROJECT_KEY:-}" ]]; then
  echo "error: LD_PROJECT_KEY is required" >&2
  exit 1
fi

if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "error: LD_ENVIRONMENT_KEY is required" >&2
  exit 1
fi

api() {
  local method="$1"
  local path="$2"
  shift 2
  local body
  local code
  body="$(mktemp)"
  code="$(curl -sS -o "${body}" -w "%{http_code}" -X "${method}" "${LD_API_HOST}/api/v2${path}" \
    -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
    -H "LD-API-Version: ${LD_API_VERSION}" \
    "$@")"
  if [[ "${code}" -ge 400 ]]; then
    echo "LaunchDarkly API error ${code}: $(cat "${body}")" >&2
    rm -f "${body}"
    return 1
  fi
  cat "${body}"
  rm -f "${body}"
}

resolve_environment_key() {
  local raw="${LD_ENVIRONMENT_KEY}"
  if [[ "${raw}" =~ ^[0-9a-f]{24}$ ]]; then
    local key
    key="$(api GET "/projects/${LD_PROJECT_KEY}/environments" | jq -r --arg id "${raw}" '.items[] | select(._id == $id) | .key' | head -1)"
    if [[ -n "${key}" ]]; then
      echo "note: LD_ENVIRONMENT_KEY is an environment id; using key \"${key}\"." >&2
      LD_ENVIRONMENT_KEY="${key}"
      export LD_ENVIRONMENT_KEY
      return 0
    fi
    echo "error: unknown environment id ${raw}" >&2
    exit 1
  fi
  if ! api GET "/projects/${LD_PROJECT_KEY}/environments/${raw}" >/dev/null 2>&1; then
    echo "error: unknown environment key \"${raw}\"" >&2
    exit 1
  fi
}

resolve_environment_key

segment_rule_patch() {
  local key="$1"
  local attribute="$2"
  local values_json="$3"
  jq -n \
    --arg env "${LD_ENVIRONMENT_KEY}" \
    --arg attr "${attribute}" \
    --argjson vals "${values_json}" \
    '{
      environmentKey: $env,
      comment: "Ensure segment targeting rule",
      instructions: [{
        kind: "addRule",
        description: "Match on context attribute",
        clauses: [{
          contextKind: "user",
          attribute: $attr,
          op: "in",
          values: $vals,
          negate: false
        }]
      }]
    }'
}

ensure_segment() {
  local key="$1"
  local name="$2"
  local attribute="$3"
  local values_json="$4"
  local segment_json rule_count patch_body

  if segment_json="$(api GET "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${key}" 2>/dev/null || true)"; then
    if echo "${segment_json}" | jq -e '.key' >/dev/null 2>&1; then
      rule_count="$(echo "${segment_json}" | jq '.rules | length')"
      if [[ "${rule_count}" -gt 0 ]]; then
        echo "  ${key}"
        return 0
      fi
      echo "  ${key} (adding rules)"
      patch_body="$(segment_rule_patch "${key}" "${attribute}" "${values_json}")"
      api PATCH "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${key}" \
        -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
        -d "${patch_body}" >/dev/null
      return 0
    fi
  fi

  echo "  ${key} (creating)"
  api POST "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
      \"key\": \"${key}\",
      \"name\": \"${name}\",
      \"tags\": [\"grid-navigator\", \"use-case\", \"segments-by-name\"],
      \"rules\": [{
        \"clauses\": [{
          \"contextKind\": \"user\",
          \"attribute\": \"${attribute}\",
          \"op\": \"in\",
          \"values\": ${values_json},
          \"negate\": false
        }]
      }]
    }" >/dev/null
}
