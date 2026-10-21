#!/usr/bin/env bash
# One-shot provision for the capstone keys only.
# Does not touch equity-briefing-completion or equity-briefing-graph.
# Requires: LD_API_ACCESS_TOKEN, LD_PROJECT_KEY
# Targeting also needs LD_ENVIRONMENT_KEY.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/create-tools.sh"
"${SCRIPT_DIR}/create-nodes.sh"
"${SCRIPT_DIR}/create-graph.sh"
"${SCRIPT_DIR}/create-judges.sh"

echo
echo "Provision complete."
echo "  Graph: equity-briefing-capstone"
echo "  Node:  cd ../node && npm install && npm start"
echo "  Open:  http://127.0.0.1:8291/"
