#!/usr/bin/env bash
# Create the custom numeric latency metric used by the adaptive trigger.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

existing="$(api GET "/metrics/${LD_PROJECT_KEY}/${METRIC_KEY}" 2>/dev/null || true)"
if jq -e '.key' >/dev/null 2>&1 <<<"${existing}"; then
  echo "Metric ${METRIC_KEY} already exists."
  jq '{key, name, kind, eventKey, isNumeric, successCriteria}' <<<"${existing}"
  exit 0
fi

echo "Creating metric ${METRIC_KEY} (event key ${EVENT_KEY})..."
api POST "/metrics/${LD_PROJECT_KEY}" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg key "${METRIC_KEY}" \
    --arg eventKey "${EVENT_KEY}" \
    '{
      key: $key,
      name: "Adaptive: grid navigation latency",
      description: "Reported navigation latency for the adaptive-trigger lab. Lower is better.",
      kind: "custom",
      isNumeric: true,
      eventKey: $eventKey,
      unit: "milliseconds",
      successCriteria: "LowerThanBaseline",
      analysisUnits: ["user"],
      unitAggregationType: "average",
      analysisType: "mean",
      tags: ["grid-navigator", "use-case", "adaptive-triggers", "latency"]
    }')" | jq '{key, name, kind, eventKey, isNumeric, successCriteria}'
