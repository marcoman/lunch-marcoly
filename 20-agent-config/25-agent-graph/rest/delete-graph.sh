#!/usr/bin/env bash
# Delete agent graph equity-briefing-graph (nodes left intact unless --nodes).
# Usage:
#   ./delete-graph.sh
#   ./delete-graph.sh --nodes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

DELETE_NODES=0
if [[ "${1:-}" == "--nodes" ]]; then
  DELETE_NODES=1
fi

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/agent-graphs/${LD_GRAPH_KEY}")"
if [[ "$STATUS" == "200" ]]; then
  echo "Deleting agent graph ${LD_GRAPH_KEY}..."
  api_ok DELETE "/projects/${LD_PROJECT_KEY}/agent-graphs/${LD_GRAPH_KEY}" >/dev/null
  echo "Deleted graph."
else
  echo "Graph ${LD_GRAPH_KEY} not found (HTTP ${STATUS}) — skip."
fi

if [[ "$DELETE_NODES" -eq 1 ]]; then
  for key in \
    "$LD_NODE_ASSESS" \
    "$LD_NODE_REPORT" \
    "$LD_NODE_QUESTIONS" \
    "$LD_NODE_GOOD" \
    "$LD_NODE_JOKE" \
    "$LD_NODE_FINALIZE"
  do
    s="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${key}")"
    if [[ "$s" == "200" ]]; then
      echo "Deleting node config ${key}..."
      api_ok DELETE "/projects/${LD_PROJECT_KEY}/ai-configs/${key}" >/dev/null
    else
      echo "skip: ${key} (HTTP ${s})"
    fi
  done
fi

echo "Done."
