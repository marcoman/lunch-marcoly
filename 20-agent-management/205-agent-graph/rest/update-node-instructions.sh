#!/usr/bin/env bash
# PATCH agent-node instructions from rest/messages/*.txt
# Usage:
#   ./update-node-instructions.sh                 # assess + good + joke + finalize
#   ./update-node-instructions.sh good joke
# https://launchdarkly.com/docs/api/agent-control/patch-ai-config-variation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

MESSAGES_DIR="${SCRIPT_DIR}/messages"

role_to_key() {
  case "$1" in
    assess) echo "$LD_NODE_ASSESS" ;;
    good) echo "$LD_NODE_GOOD" ;;
    joke) echo "$LD_NODE_JOKE" ;;
    finalize) echo "$LD_NODE_FINALIZE" ;;
    questions) echo "$LD_NODE_QUESTIONS" ;;
    *) echo "" ;;
  esac
}

role_to_file() {
  case "$1" in
    assess) echo "assess-instructions.txt" ;;
    good) echo "good-instructions.txt" ;;
    joke) echo "joke-instructions.txt" ;;
    finalize) echo "finalize-instructions.txt" ;;
    questions) echo "questions-instructions.txt" ;;
    *) echo "" ;;
  esac
}

if [[ $# -eq 0 ]]; then
  set -- assess good joke finalize
fi

for role in "$@"; do
  key="$(role_to_key "$role")"
  file="$(role_to_file "$role")"
  if [[ -z "$key" || -z "$file" ]]; then
    echo "error: unknown role '$role' (assess|good|joke|finalize|questions)" >&2
    exit 1
  fi
  path="${MESSAGES_DIR}/${file}"
  if [[ ! -f "$path" ]]; then
    echo "error: missing $path" >&2
    exit 1
  fi

  echo "==> ${role} → ${key}"
  CFG="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${key}")"
  # Collect variation keys first (avoid pipe subshell issues).
  VKEYS="$(echo "$CFG" | jq -r '.variations[]?.key // empty')"
  if [[ -z "$VKEYS" ]]; then
    echo "error: no variations on ${key}" >&2
    exit 1
  fi
  while IFS= read -r vkey; do
    [[ -z "$vkey" ]] && continue
    echo "  variation ${vkey}"
    api_ok PATCH "/projects/${LD_PROJECT_KEY}/ai-configs/${key}/variations/${vkey}" \
      -H "Content-Type: application/json" \
      -d "$(jq -n --rawfile instructions "$path" \
        '{instructions: ($instructions | gsub("\\n$"; ""))}')" \
      | jq -r --arg role "$role" --arg v "$vkey" \
        '"\($role)/\($v): " + ((.instructions // "")[0:80]) + "…"'
  done <<< "$VKEYS"
done

echo "Done."
