#!/usr/bin/env bash
# Shared LaunchDarkly REST helpers for 16-percentage-rollout.
# https://launchdarkly.com/docs/guides/api/rest-api
set -euo pipefail

: "${LD_API_HOST:=https://app.launchdarkly.com}"
: "${LD_API_VERSION:=20240415}"

if [[ -z "${LD_API_ACCESS_TOKEN:-}" || -z "${LD_PROJECT_KEY:-}" ]]; then
  echo "error: LD_API_ACCESS_TOKEN and LD_PROJECT_KEY are required" >&2
  exit 1
fi

FLAG_KEY="enable-grid-selection-highlight-pct"

api() {
  local method="$1" path="$2"
  shift 2
  curl -sS -X "$method" "${LD_API_HOST}/api/v2${path}" \
    -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
    -H "LD-API-Version: ${LD_API_VERSION}" "$@"
}

api_status() {
  local method="$1" path="$2"
  shift 2
  curl -sS -o /dev/null -w "%{http_code}" -X "$method" \
    "${LD_API_HOST}/api/v2${path}" \
    -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
    -H "LD-API-Version: ${LD_API_VERSION}" "$@"
}

require_environment() {
  if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
    echo "error: LD_ENVIRONMENT_KEY is required for rollout targeting" >&2
    exit 1
  fi
}

fetch_flag() {
  api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}?env=${LD_ENVIRONMENT_KEY}"
}

variation_id() {
  local flag_json="$1" value="$2"
  jq -er --arg value "$value" \
    '.variations[] | select(.value == $value) | ._id' <<<"$flag_json"
}
