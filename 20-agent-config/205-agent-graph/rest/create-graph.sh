#!/usr/bin/env bash
# Create agent graph equity-briefing-graph (assess → specialists → finalize).
# LaunchDarkly: Agent graphs · rootConfigKey · edges
# https://launchdarkly.com/docs/api/ai-configs/post-agent-graph
# https://launchdarkly.com/docs/home/agentcontrol/agent-graphs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/agent-graphs/${LD_GRAPH_KEY}")"
if [[ "$STATUS" == "200" ]]; then
  echo "error: agent graph ${LD_GRAPH_KEY} already exists." >&2
  echo "Delete it first: ./delete-graph.sh" >&2
  exit 1
fi

echo "==> Agent graph ${LD_GRAPH_KEY}"
BODY="$(jq -n \
  --arg key "$LD_GRAPH_KEY" \
  --arg name "$LD_GRAPH_NAME" \
  --arg root "$LD_NODE_ASSESS" \
  --arg report "$LD_NODE_REPORT" \
  --arg questions "$LD_NODE_QUESTIONS" \
  --arg good "$LD_NODE_GOOD" \
  --arg joke "$LD_NODE_JOKE" \
  --arg finalize "$LD_NODE_FINALIZE" \
  '{
    key: $key,
    name: $name,
    description: "Classroom graph: assess → specialist → finalize",
    rootConfigKey: $root,
    edges: [
      { key: "to-report", sourceConfig: $root, targetConfig: $report },
      { key: "to-questions", sourceConfig: $root, targetConfig: $questions },
      { key: "to-good", sourceConfig: $root, targetConfig: $good },
      { key: "to-joke", sourceConfig: $root, targetConfig: $joke },
      { key: "report-to-finalize", sourceConfig: $report, targetConfig: $finalize },
      { key: "questions-to-finalize", sourceConfig: $questions, targetConfig: $finalize },
      { key: "good-to-finalize", sourceConfig: $good, targetConfig: $finalize },
      { key: "joke-to-finalize", sourceConfig: $joke, targetConfig: $finalize }
    ]
  }')"

api_ok POST "/projects/${LD_PROJECT_KEY}/agent-graphs" \
  -H "Content-Type: application/json" \
  -d "$BODY" | jq '{key, name, rootConfigKey, edges: [.edges[]? | {key, sourceConfig, targetConfig}]}'

echo "Done. Graph key: ${LD_GRAPH_KEY}"
echo "UI: ${LD_API_HOST}/projects/${LD_PROJECT_KEY}/agent-graphs/${LD_GRAPH_KEY}"
echo "Pull: ollama pull ${LD_MODEL_ID} && ollama pull ${LD_MODEL_SIMPLE_ID}"
