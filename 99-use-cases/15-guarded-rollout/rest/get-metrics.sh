#!/usr/bin/env bash
# List the guarded-rollout guardrail metrics.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

for key in grid-nav-latency grid-highlight-error-rate grid-nav-movement; do
  echo "=== ${key} ==="
  api GET "/metrics/${LD_PROJECT_KEY}/${key}" | jq '{
    key,
    name,
    kind,
    eventKey,
    isNumeric,
    successCriteria,
    unit,
    unitAggregationType,
    analysisUnits
  }'
  echo
done
