#!/usr/bin/env bash
# Shared LaunchDarkly REST helpers.
# https://launchdarkly.com/docs/guides/api/rest-api

set -euo pipefail

: "${LD_API_HOST:=https://app.launchdarkly.com}"
: "${LD_API_VERSION:=20240415}"

for name in LD_API_ACCESS_TOKEN LD_PROJECT_KEY; do
  if [[ -z "${!name:-}" ]]; then
    echo "error: ${name} is required" >&2
    exit 1
  fi
done

require_environment() {
  if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
    echo "error: LD_ENVIRONMENT_KEY is required" >&2
    exit 1
  fi
}

require_jq() {
  command -v jq >/dev/null 2>&1 || {
    echo "error: jq is required" >&2
    exit 1
  }
}

urlencode() {
  jq -rn --arg value "$1" '$value|@uri'
}

api_request() {
  local method="$1" path="$2" output http
  shift 2
  output="$(mktemp)"
  http="$(curl -sS -X "$method" "${LD_API_HOST%/}/api/v2${path}" \
    -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
    -H "LD-API-Version: ${LD_API_VERSION}" \
    -o "$output" -w '%{http_code}' "$@")"
  API_HTTP_STATUS="$http"
  API_RESPONSE="$(cat "$output")"
  rm -f "$output"
}

api_ok() {
  api_request "$@"
  if (( API_HTTP_STATUS < 200 || API_HTTP_STATUS >= 300 )); then
    echo "error: $1 $2 returned HTTP ${API_HTTP_STATUS}" >&2
    jq . <<<"$API_RESPONSE" 2>/dev/null || printf '%s\n' "$API_RESPONSE" >&2
    return 1
  fi
  printf '%s' "$API_RESPONSE"
}
