#!/usr/bin/env bash
# Shared helpers for AgentControl REST API examples.
# LaunchDarkly: AgentControl configs · AI model configs · semantic patch targeting
# https://launchdarkly.com/docs/api/agent-control
# https://launchdarkly.com/docs/guides/api/rest-api

set -euo pipefail

: "${LD_API_HOST:=https://app.launchdarkly.com}"
# AgentControl endpoints are under the beta API version.
: "${LD_API_VERSION:=beta}"

: "${LD_CONFIG_KEY:=equity-briefing-completion}"
: "${LD_CONFIG_NAME:=Equity briefing completion}"
: "${LD_MODEL_CONFIG_KEY:=Custom.llama3.2-3b}"
: "${LD_MODEL_ID:=llama3.2:3b}"
: "${LD_MODEL_DISPLAY_NAME:=Ollama llama3.2:3b}"
: "${LD_MODEL_PROVIDER:=Custom}"

if [[ -z "${LD_API_ACCESS_TOKEN:-}" ]]; then
  echo "error: LD_API_ACCESS_TOKEN is required" >&2
  exit 1
fi

if [[ -z "${LD_PROJECT_KEY:-}" ]]; then
  echo "error: LD_PROJECT_KEY is required" >&2
  exit 1
fi

# curl wrapper for /api/v2{path}. Extra args are passed through (headers, -d, …).
api() {
  local method="$1"
  local path="$2"
  shift 2

  curl -sS -X "$method" "${LD_API_HOST}/api/v2${path}" \
    -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
    -H "LD-API-Version: ${LD_API_VERSION}" \
    "$@"
}

# Like api(), but prints the body and exits non-zero on non-2xx responses.
api_ok() {
  local method="$1"
  local path="$2"
  shift 2

  local tmp http body
  tmp="$(mktemp)"
  http="$(
    curl -sS -X "$method" "${LD_API_HOST}/api/v2${path}" \
      -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
      -H "LD-API-Version: ${LD_API_VERSION}" \
      -o "$tmp" -w "%{http_code}" \
      "$@"
  )"
  body="$(cat "$tmp")"
  rm -f "$tmp"

  if [[ "$http" -lt 200 || "$http" -ge 300 ]]; then
    echo "error: ${method} ${path} → HTTP ${http}" >&2
    echo "$body" | jq . 2>/dev/null || echo "$body" >&2
    exit 1
  fi
  printf '%s' "$body"
}

# HTTP status only (no body). Useful for existence checks.
api_status() {
  local method="$1"
  local path="$2"
  shift 2

  curl -sS -X "$method" "${LD_API_HOST}/api/v2${path}" \
    -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
    -H "LD-API-Version: ${LD_API_VERSION}" \
    -o /dev/null -w "%{http_code}" \
    "$@"
}

require_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    echo "error: jq is required" >&2
    exit 1
  fi
}

require_environment() {
  if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
    echo "error: LD_ENVIRONMENT_KEY is required for targeting" >&2
    exit 1
  fi
}
