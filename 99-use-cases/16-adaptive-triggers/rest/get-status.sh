#!/usr/bin/env bash
# Show flag targeting and the custom metric used by the adaptive trigger.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

echo "Flag ${FLAG_KEY}:"
fetch_flag | jq \
  --arg env "${LD_ENVIRONMENT_KEY}" \
  '. as $flag | $flag.environments[$env] |
   {on, offVariation, fallthrough,
    variations: [$flag.variations[] | {value, _id}]}'

echo
echo "Metric ${METRIC_KEY}:"
api GET "/metrics/${LD_PROJECT_KEY}/${METRIC_KEY}" |
  jq '{key, name, kind, eventKey, isNumeric, unit, successCriteria}'

echo
echo "Adaptive trigger configuration is visible on the flag Targeting tab."
