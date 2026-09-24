#!/usr/bin/env bash
# Create the custom conversion metric if it is absent.
# Metrics — custom, non-numeric conversion:
# https://launchdarkly.com/docs/api/metrics/post-metric

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

METRIC_KEY="mobile_onboarding_completed"
project="$(urlencode "$LD_PROJECT_KEY")"
metric="$(urlencode "$METRIC_KEY")"

api_request GET "/metrics/${project}/${metric}"
case "$API_HTTP_STATUS" in
  200)
    echo "Metric ${METRIC_KEY} already exists; leaving it unchanged."
    jq '{key, name, kind, eventKey, isNumeric, analysisUnits}' <<<"$API_RESPONSE"
    ;;
  404)
    api_ok POST "/metrics/${project}" \
      -H "Content-Type: application/json" \
      -d "$(jq -nc '{
        key: "mobile_onboarding_completed",
        name: "Acme: mobile onboarding completed",
        description: "Conversion after the first successful orthogonal grid move.",
        kind: "custom",
        isNumeric: false,
        eventKey: "mobile_onboarding_completed",
        successCriteria: "HigherThanBaseline",
        analysisUnits: ["user"],
        tags: ["acme", "mobile", "experimentation", "onboarding"]
      }')" |
      jq '{key, name, kind, eventKey, isNumeric, analysisUnits}'
    ;;
  *)
    echo "error: unable to inspect ${METRIC_KEY} (HTTP ${API_HTTP_STATUS})" >&2
    jq . <<<"$API_RESPONSE" 2>/dev/null || printf '%s\n' "$API_RESPONSE" >&2
    exit 1
    ;;
esac
