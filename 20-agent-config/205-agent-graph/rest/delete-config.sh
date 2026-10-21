#!/usr/bin/env bash
# Delete one AI config by key (nodes). Prefer ./delete-graph.sh --nodes for cleanup.
# Usage: ./delete-config.sh <config-key>
# https://launchdarkly.com/docs/api/agent-control/delete-ai-config

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

if [[ $# -lt 1 || -z "${1:-}" ]]; then
  echo "usage: $0 <config-key>" >&2
  exit 1
fi

CONFIG_KEY="$1"

echo "Deleting AI config ${CONFIG_KEY} from project ${LD_PROJECT_KEY}..."
HTTP="$(api_status DELETE "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}")"
echo "HTTP ${HTTP}"

if [[ "$HTTP" != "204" && "$HTTP" != "200" ]]; then
  echo "error: unexpected status deleting ${CONFIG_KEY}" >&2
  exit 1
fi

echo "Done. Model configs are left in place."
