#!/usr/bin/env bash
# Shared REST helpers for 14-progressive-rollout.

set -euo pipefail

: "${LD_API_HOST:=https://app.launchdarkly.com}"
: "${LD_API_VERSION:=20240415}"

FLAG_KEY="enable-grid-selection-highlight"
BASELINE_COLOR="none"
ROLLOUT_COLOR="green"
ROLLOUT_PERCENTAGES=(10 20 40 60 100)
DEFAULT_STAGE_SECONDS=180

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

variation_id() {
  local flag_json="$1"
  local value="$2"
  echo "${flag_json}" | jq -r --arg v "${value}" '.variations[] | select(.value == $v) | ._id' | head -1
}

variation_index() {
  local flag_json="$1"
  local value="$2"
  echo "${flag_json}" | jq -r --arg v "${value}" '.variations | to_entries[] | select(.value.value == $v) | .key' | head -1
}

fetch_flag() {
  api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}"
}
