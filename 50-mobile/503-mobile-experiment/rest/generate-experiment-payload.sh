#!/usr/bin/env bash
# Generate a reviewable experiment draft; this script never creates or starts it.
# https://launchdarkly.com/docs/api/experiments/create-experiment

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

control_id="$(jq -er '.variations[] | select(.value == false) | ._id' <<<"$flag_json")"
treatment_id="$(jq -er '.variations[] | select(.value == true) | ._id' <<<"$flag_json")"
config_version="$(jq -er '.environments[$environment]._version' \
  --arg environment "$LD_ENVIRONMENT_KEY" <<<"$flag_json")"

# The API requires a rule/allocation ID in iteration.flags. That ID must come
# from the allocation configured in the dashboard, so the generated draft
# deliberately leaves a visible placeholder instead of guessing.
flags="$(jq -rnc \
  --arg key "acme-mobile-onboarding-v2" \
  --arg version "$config_version" \
  --arg fallback "$control_id" '{
    ($key): {
      ruleId: "REPLACE_WITH_DASHBOARD_ALLOCATION_RULE_ID",
      flagConfigVersion: ($version | tonumber),
      notInExperimentVariationId: $fallback
    }
  } | tostring')"

jq -n \
  --arg control "$control_id" \
  --arg treatment "$treatment_id" \
  --arg flags "$flags" \
  --arg metric "$(jq -r '.key' <<<"$metric_json")" '{
    name: "First-run helper vs grid",
    key: "first-run-helper-vs-grid",
    iteration: {
      hypothesis: "If we show a short How to play card before the 2×2 grid, then more users will complete their first successful orthogonal move than users who open the grid immediately, because the card gives them greater confidence.",
      metrics: [{key: $metric, isGroup: false}],
      primarySingleMetricKey: $metric,
      randomizationUnit: "user",
      attributes: ["platform", "app-version"],
      treatments: [
        {
          name: "Control",
          baseline: true,
          allocationPercent: "50",
          parameters: [{
            flagKey: "acme-mobile-onboarding-v2",
            variationId: $control
          }]
        },
        {
          name: "Treatment",
          baseline: false,
          allocationPercent: "50",
          parameters: [{
            flagKey: "acme-mobile-onboarding-v2",
            variationId: $treatment
          }]
        }
      ],
      flags: $flags
    }
  }'
