#!/usr/bin/env bash
# Inspect the flag, selected environment, and conversion metric.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

project="$(urlencode "$LD_PROJECT_KEY")"
environment="$(urlencode "$LD_ENVIRONMENT_KEY")"
flag_json="$(api_ok GET "/flags/${project}/acme-mobile-onboarding-v2?env=${environment}")"
metric_json="$(api_ok GET "/metrics/${project}/mobile_onboarding_completed")"

jq -n \
  --arg environment "$LD_ENVIRONMENT_KEY" \
  --argjson flag "$flag_json" \
  --argjson metric "$metric_json" '{
    environment: $environment,
    flag: {
      key: $flag.key,
      mobileAvailable: $flag.clientSideAvailability.usingMobileKey,
      variations: [$flag.variations[] | {id: ._id, name, value}],
      targeting: $flag.environments[$environment]
    },
    metric: {
      key: $metric.key,
      kind: $metric.kind,
      eventKey: $metric.eventKey,
      isNumeric: $metric.isNumeric,
      analysisUnits: $metric.analysisUnits
    }
  }'
