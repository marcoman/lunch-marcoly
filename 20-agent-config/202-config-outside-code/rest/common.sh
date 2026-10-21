#!/usr/bin/env bash
# Shared helpers for 22-config-outside-code AgentControl REST scripts.
# LaunchDarkly: AgentControl · tracked completion · AI metrics
# https://launchdarkly.com/docs/api/agent-control
# https://launchdarkly.com/docs/guides/api/rest-api

set -euo pipefail

: "${LD_API_HOST:=https://app.launchdarkly.com}"
: "${LD_API_VERSION:=beta}"

: "${LD_CONFIG_KEY:=equity-briefing-tracked-completion}"
: "${LD_CONFIG_NAME:=Equity briefing tracked completion}"
: "${LD_MODEL_PROVIDER:=Custom}"

# Default / anonymous → smallest Ollama
: "${LD_MODEL_OLLAMA_CONFIG_KEY:=Custom.llama3.2-1b}"
: "${LD_MODEL_OLLAMA_ID:=llama3.2:1b}"
: "${LD_MODEL_OLLAMA_DISPLAY_NAME:=Ollama llama3.2:1b (tracked default)}"

# Best Betty → Anthropic Claude (built-in model id; no Custom model config)
: "${LD_ANTHROPIC_MODEL_ID:=claude-sonnet-5}"

# Aliases used by create-model-config.sh one-shot defaults
: "${LD_MODEL_CONFIG_KEY:=${LD_MODEL_OLLAMA_CONFIG_KEY}}"
: "${LD_MODEL_ID:=${LD_MODEL_OLLAMA_ID}}"
: "${LD_MODEL_DISPLAY_NAME:=${LD_MODEL_OLLAMA_DISPLAY_NAME}}"

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
    echo "LaunchDarkly API error ${http}: ${body}" >&2
    exit 1
  fi
  printf '%s' "$body"
}

api_status() {
  local method="$1"
  local path="$2"
  shift 2
  curl -sS -o /dev/null -w "%{http_code}" -X "$method" "${LD_API_HOST}/api/v2${path}" \
    -H "Authorization: ${LD_API_ACCESS_TOKEN}" \
    -H "LD-API-Version: ${LD_API_VERSION}" \
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
