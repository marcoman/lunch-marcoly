#!/usr/bin/env bash
# Shared REST helpers for 16-adaptive-triggers.

set -euo pipefail

: "${LD_API_HOST:=https://app.launchdarkly.com}"
: "${LD_API_VERSION:=20240415}"

FLAG_KEY="enable-adaptive-grid-highlight"
METRIC_KEY="adaptive-grid-nav-latency-metric"
EVENT_KEY="adaptive-grid-nav-latency"
SAFE_COLOR="none"
LIVE_COLOR="green"

for variable in LD_API_ACCESS_TOKEN LD_PROJECT_KEY LD_ENVIRONMENT_KEY; do
  if [[ -z "${!variable:-}" ]]; then
    echo "error: ${variable} is required" >&2
    exit 1
  fi
done

api() {
  local method="$1"
  local path="$2"
  shift 2
  local body code
  body="$(mktemp)"
  code="$(curl -sS -o "${body}" -w "%{http_code}" -X "${method}" \
    "${LD_API_HOST}/api/v2${path}" \
    -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
    -H "LD-API-Version: ${LD_API_VERSION}" "$@")"
  if [[ "${code}" -ge 400 ]]; then
    echo "LaunchDarkly API error ${code}: $(<"${body}")" >&2
    rm -f "${body}"
    return 1
  fi
  command cat "${body}"
  rm -f "${body}"
}

fetch_flag() {
  api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}"
}

variation_id() {
  local flag_json="$1"
  local value="$2"
  jq -r --arg value "${value}" \
    '.variations[] | select(.value == $value) | ._id' <<<"${flag_json}"
}
