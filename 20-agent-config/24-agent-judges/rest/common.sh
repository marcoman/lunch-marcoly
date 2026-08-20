#!/usr/bin/env bash
# Shared helpers for 24-agent-judges REST provisioning.
# LaunchDarkly: AgentControl · Judges · completion configs
# https://launchdarkly.com/docs/api/agent-control
# https://launchdarkly.com/docs/home/agentcontrol/judges

set -euo pipefail

: "${LD_API_HOST:=https://app.launchdarkly.com}"
: "${LD_API_VERSION:=beta}"

: "${LD_CONFIG_KEY:=equity-briefing-judged}"
: "${LD_CONFIG_NAME:=Equity briefing judged}"

: "${LD_JUDGE_FIDELITY_KEY:=equity-briefing-source-fidelity}"
: "${LD_JUDGE_FIDELITY_NAME:=Equity briefing source fidelity}"
# Metric keys must use the $ld:ai:judge: prefix (API 400 otherwise).
: "${LD_JUDGE_FIDELITY_METRIC:=\$ld:ai:judge:source-fidelity}"

: "${LD_JUDGE_DISCIPLINE_KEY:=equity-briefing-recommendation-discipline}"
: "${LD_JUDGE_DISCIPLINE_NAME:=Equity briefing recommendation discipline}"
: "${LD_JUDGE_DISCIPLINE_METRIC:=\$ld:ai:judge:recommendation-discipline}"

: "${LD_MODEL_PROVIDER:=Custom}"

# Judges (stay mid-tier so Charlie's bigger rewrite is the visible upgrade)
: "${LD_MODEL_BEST_CONFIG_KEY:=Custom.llama3.2-3b}"
: "${LD_MODEL_BEST_ID:=llama3.2:3b}"
: "${LD_MODEL_BEST_DISPLAY_NAME:=Ollama llama3.2:3b (judges)}"

# Charlie / concise-skeptic rewrite — stronger local model
: "${LD_MODEL_REWRITE_CONFIG_KEY:=Custom.llama3.1-8b}"
: "${LD_MODEL_REWRITE_ID:=llama3.1:8b}"
: "${LD_MODEL_REWRITE_DISPLAY_NAME:=Ollama llama3.1:8b (Charlie rewrite)}"

# Toby draft
: "${LD_MODEL_SIMPLE_CONFIG_KEY:=Custom.llama3.2-1b}"
: "${LD_MODEL_SIMPLE_ID:=llama3.2:1b}"
: "${LD_MODEL_SIMPLE_DISPLAY_NAME:=Ollama llama3.2:1b (simple)}"

: "${LD_MODEL_CONFIG_KEY:=${LD_MODEL_REWRITE_CONFIG_KEY}}"
: "${LD_MODEL_ID:=${LD_MODEL_REWRITE_ID}}"
: "${LD_MODEL_DISPLAY_NAME:=${LD_MODEL_REWRITE_DISPLAY_NAME}}"

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
    # Prefer a readable message field when present (e.g. judge metric-key validation).
    if echo "$body" | jq -e 'type == "object" and (.message // .error // .code)' >/dev/null 2>&1; then
      echo "$body" | jq -r '.message // .error // .code // .' >&2
    fi
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
