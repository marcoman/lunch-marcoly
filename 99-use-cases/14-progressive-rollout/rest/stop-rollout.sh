#!/usr/bin/env bash
# Stop the rollout — turn flag off (all users receive none).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/set-rollout-percent.sh" 0
