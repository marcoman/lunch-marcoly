#!/usr/bin/env bash
# Shared helpers for 25-agent-graph REST provisioning.
# LaunchDarkly: AgentControl · Agent graphs · Agents
# https://launchdarkly.com/docs/api/agent-control
# https://launchdarkly.com/docs/home/agentcontrol/agent-graphs

set -euo pipefail

: "${LD_API_HOST:=https://app.launchdarkly.com}"
: "${LD_API_VERSION:=beta}"

: "${LD_GRAPH_KEY:=equity-briefing-graph}"
: "${LD_GRAPH_NAME:=Equity briefing graph}"

: "${LD_NODE_ASSESS:=equity-briefing-graph-assess}"
: "${LD_NODE_REPORT:=equity-briefing-graph-report}"
: "${LD_NODE_QUESTIONS:=equity-briefing-graph-questions}"
: "${LD_NODE_GOOD:=equity-briefing-graph-good}"
: "${LD_NODE_JOKE:=equity-briefing-graph-joke}"
: "${LD_NODE_FINALIZE:=equity-briefing-graph-finalize}"

: "${LD_MODEL_PROVIDER:=Custom}"
: "${LD_MODEL_CONFIG_KEY:=Custom.llama3.2-3b}"
: "${LD_MODEL_ID:=llama3.2:3b}"
: "${LD_MODEL_DISPLAY_NAME:=Ollama llama3.2:3b (graph)}"

: "${LD_MODEL_SIMPLE_CONFIG_KEY:=Custom.llama3.2-1b}"
: "${LD_MODEL_SIMPLE_ID:=llama3.2:1b}"
: "${LD_MODEL_SIMPLE_DISPLAY_NAME:=Ollama llama3.2:1b (Toby report)}"

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
