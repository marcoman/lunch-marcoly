#!/usr/bin/env bash
# LaunchDarkly capability: AgentControl — delete AI config
# Permanently deletes a config and its variations. Does not delete model configs.
# https://launchdarkly.com/docs/api/agent-control/delete-ai-config

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

CONFIG_KEY="${1:-$LD_CONFIG_KEY}"

echo "Deleting AI config ${CONFIG_KEY} from project ${LD_PROJECT_KEY}..."
HTTP="$(api_status DELETE "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}")"
echo "HTTP ${HTTP}"

if [[ "$HTTP" != "204" && "$HTTP" != "200" ]]; then
  echo "error: unexpected status deleting ${CONFIG_KEY}" >&2
  exit 1
fi

echo "Done. Model configs and Library tools are left in place."
echo "Re-create with: ./create-config.sh"
