#!/usr/bin/env bash
# Create the three guarded-rollout guardrail metrics in LaunchDarkly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

fetch_metric() {
  api GET "/metrics/${LD_PROJECT_KEY}/${1}" 2>/dev/null || true
}

ensure_metric() {
  local key="$1"
  local body="$2"

  if existing="$(fetch_metric "${key}")"; then
    if echo "${existing}" | jq -e '.key' >/dev/null 2>&1; then
      echo "Metric ${key} already exists."
      echo "${existing}" | jq '{key, name, kind, eventKey, isNumeric, successCriteria}'
      return 0
    fi
  fi

  echo "Creating metric ${key}..."
  api POST "/metrics/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d "${body}" | jq '{key, name, kind, eventKey, isNumeric, successCriteria}'
}

ensure_metric "grid-nav-latency" "$(jq -n '{
  key: "grid-nav-latency",
  name: "Grid navigation latency",
  description: "Milliseconds from navigation input to grid update when green highlight is enabled. Guardrail threshold: 200 ms.",
  kind: "custom",
  isNumeric: true,
  eventKey: "grid-navigation-latency",
  unit: "milliseconds",
  successCriteria: "LowerThanBaseline",
  analysisUnits: ["user"],
  unitAggregationType: "average",
  analysisType: "mean",
  tags: ["grid-navigator", "use-case", "guarded-rollout", "latency"]
}')"

ensure_metric "grid-highlight-error-rate" "$(jq -n '{
  key: "grid-highlight-error-rate",
  name: "Grid highlight error rate",
  description: "Incorrect highlight color displayed when green highlight is enabled. Guardrail threshold: 0% error rate.",
  kind: "custom",
  isNumeric: false,
  eventKey: "grid-highlight-color-error",
  successCriteria: "LowerThanBaseline",
  analysisUnits: ["user"],
  tags: ["grid-navigator", "use-case", "guarded-rollout", "error-rate"]
}')"

ensure_metric "grid-nav-movement" "$(jq -n '{
  key: "grid-nav-movement",
  name: "Grid navigation movement",
  description: "Number of grid navigations per user session. Guardrail threshold: at least 1 navigation.",
  kind: "custom",
  isNumeric: true,
  eventKey: "grid-navigation-count",
  unit: "navigations",
  successCriteria: "HigherThanBaseline",
  analysisUnits: ["user"],
  unitAggregationType: "sum",
  analysisType: "mean",
  tags: ["grid-navigator", "use-case", "guarded-rollout", "movement"]
}')"

echo
echo "Done. Attach these metrics with ./configure-guarded-rollout.sh"
