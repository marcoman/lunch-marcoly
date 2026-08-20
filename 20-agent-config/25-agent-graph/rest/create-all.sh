#!/usr/bin/env bash
# One-shot provision: model configs → node agent configs → graph.
# Requires: LD_API_ACCESS_TOKEN, LD_PROJECT_KEY; LD_ENVIRONMENT_KEY for targeting.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/create-nodes.sh"
"${SCRIPT_DIR}/create-graph.sh"

echo
echo "Provision complete."
echo "  Graph:  equity-briefing-graph"
echo "  Python: cd ../python && python 25-agent-graph.py"
