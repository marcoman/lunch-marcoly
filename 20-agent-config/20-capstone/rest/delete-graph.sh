#!/usr/bin/env bash
# Delete agent graph equity-briefing-capstone.
# Usage:
#   ./delete-graph.sh
#   ./delete-graph.sh --nodes    # also delete node configs and the two judges
#   ./delete-graph.sh --tools    # also delete the three Library tools
#   ./delete-graph.sh --nodes --tools

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

DELETE_NODES=0
DELETE_TOOLS=0
for arg in "$@"; do
  case "$arg" in
    --nodes) DELETE_NODES=1 ;;
    --tools) DELETE_TOOLS=1 ;;
    *)
      echo "error: unknown argument ${arg}" >&2
      exit 1
      ;;
  esac
done

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
    "$LD_NODE_FINALIZE" \
    "$LD_JUDGE_FIDELITY_KEY" \
    "$LD_JUDGE_DISCIPLINE_KEY"
  do
    s="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${key}")"
    if [[ "$s" == "200" ]]; then
      echo "Deleting config ${key}..."
      api_ok DELETE "/projects/${LD_PROJECT_KEY}/ai-configs/${key}" >/dev/null
    else
      echo "skip: ${key} (HTTP ${s})"
    fi
  done
fi

if [[ "$DELETE_TOOLS" -eq 1 ]]; then
  for key in "$LD_TOOL_PIG_LATIN" "$LD_TOOL_ROT13" "$LD_TOOL_JOKE_TAGLINE"; do
    s="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-tools/${key}")"
    if [[ "$s" == "200" ]]; then
      echo "Deleting tool ${key}..."
      api_ok DELETE "/projects/${LD_PROJECT_KEY}/ai-tools/${key}" >/dev/null
    else
      echo "skip: tool ${key} (HTTP ${s})"
    fi
  done
fi

echo "Done."
