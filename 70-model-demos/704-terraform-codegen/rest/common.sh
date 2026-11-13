#!/usr/bin/env bash
# Shared helpers for the terraform-codegen AgentControl config.
# LaunchDarkly: AgentControl configs · AI model configs · semantic patch targeting
# https://launchdarkly.com/docs/api/agent-control
# https://launchdarkly.com/docs/guides/api/rest-api

set -euo pipefail

: "${LD_API_HOST:=https://app.launchdarkly.com}"
# AgentControl endpoints are under the beta API version.
: "${LD_API_VERSION:=beta}"

: "${LD_CONFIG_KEY:=terraform-codegen-compare}"
: "${LD_CONFIG_NAME:=Terraform codegen compare}"
: "${LD_MODEL_PROVIDER:=Custom}"

# Inexpensive local, local ceiling, and a mid model that the screen leaves unchecked.
: "${LD_MODEL_SMALL_CONFIG_KEY:=Custom.llama3.2-1b}"
: "${LD_MODEL_SMALL_ID:=llama3.2:1b}"
: "${LD_MODEL_SMALL_DISPLAY_NAME:=Ollama llama3.2:1b}"

: "${LD_MODEL_LARGE_CONFIG_KEY:=Custom.llama3.2-3b}"
: "${LD_MODEL_LARGE_ID:=llama3.2:3b}"
: "${LD_MODEL_LARGE_DISPLAY_NAME:=Ollama llama3.2:3b}"

: "${LD_MODEL_CEILING_CONFIG_KEY:=Custom.llama3.1-8b}"
: "${LD_MODEL_CEILING_ID:=llama3.1:8b}"
: "${LD_MODEL_CEILING_DISPLAY_NAME:=Ollama llama3.1:8b}"
: "${LD_MODEL_CEILING_VARIATION_KEY:=local-8b}"

# Built-in model ids. No Custom model config. The app calls Anthropic after the variation is served.
: "${LD_HAIKU_MODEL_ID:=claude-haiku-4-5-20251001}"
: "${LD_HAIKU_VARIATION_KEY:=claude-haiku}"
: "${LD_ANTHROPIC_MODEL_ID:=claude-sonnet-5}"
: "${LD_ANTHROPIC_VARIATION_KEY:=claude-sonnet}"

# Separate judge config. Sonnet scores the file. The generator does not grade itself.
: "${LD_JUDGE_KEY:=terraform-codegen-judge}"
: "${LD_JUDGE_NAME:=Terraform codegen judge}"
: "${LD_JUDGE_MODEL_ID:=claude-sonnet-5}"
: "${LD_JUDGE_METRIC:=\$ld:ai:judge:terraform-brief}"

if [[ -z "${LD_API_ACCESS_TOKEN:-}" ]]; then
  echo "error: LD_API_ACCESS_TOKEN is required" >&2
  exit 1
fi

if [[ -z "${LD_PROJECT_KEY:-}" ]]; then
  echo "error: LD_PROJECT_KEY is required" >&2
  exit 1
fi

api() {
  local method="$1"
  local path="$2"
  shift 2

  curl -sS -X "$method" "${LD_API_HOST}/api/v2${path}" \
    -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
    -H "LD-API-Version: ${LD_API_VERSION}" \
    "$@"
}

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
