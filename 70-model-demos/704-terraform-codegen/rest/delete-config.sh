#!/usr/bin/env bash
# Delete terraform-codegen-compare. Leaves shared Ollama model configs in place.
# https://launchdarkly.com/docs/api/agent-control/delete-ai-config

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}")"
if [[ "$STATUS" == "404" ]]; then
  echo "AI config ${LD_CONFIG_KEY} is already gone."
  exit 0
fi

api_ok DELETE "/projects/${LD_PROJECT_KEY}/ai-configs/${LD_CONFIG_KEY}" >/dev/null
echo "Deleted ${LD_CONFIG_KEY}."
