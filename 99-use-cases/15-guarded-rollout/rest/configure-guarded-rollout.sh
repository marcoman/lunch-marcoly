#!/usr/bin/env bash
# Prepare guardrail metrics and guarded-rollout targeting for the LaunchDarkly UI.
#
# In this example, we have a guarded rollout over 12 minutes in four equal
# stages: 10%, 20%, 30%, and 50% of users receive the green highlight.
#
# Fallback / baseline variation: "none" (no highlight).
#
# NOTE: LaunchDarkly's public REST semantic-patch API does not start guarded
# rollouts — guardedRolloutConfig is ignored on updateFallthroughVariationOrRollout.
# Configure the guarded rollout in the UI (or paste the generated JSON into the
# flag's JSON targeting editor). This script creates metrics, prepares the flag,
# and prints the targeting JSON.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

STAGE_SECONDS="${STAGE_SECONDS:-${DEFAULT_STAGE_SECONDS}}"
AUTO_ROLLBACK="${AUTO_ROLLBACK:-true}"
ENSURE_METRICS="${ENSURE_METRICS:-true}"
PREP_FLAG="${PREP_FLAG:-true}"
DRY_RUN=false

usage() {
  cat <<EOF
usage: $0 [--dry-run] [--skip-metrics] [--no-prep-flag]

Prepare guardrail metrics and guarded-rollout targeting for ${FLAG_KEY}.

This script does NOT start a guarded rollout via REST. After it runs, complete
the rollout in the LaunchDarkly UI (Targeting → Default rule → Guarded rollout)
or paste the generated JSON into the JSON targeting editor.

Options:
  --dry-run       Print actions without applying them
  --skip-metrics  Do not run create-metrics.sh first
  --no-prep-flag  Do not turn the flag on or set off variation to none

Environment overrides:
  STAGE_SECONDS   Seconds per stage (default: ${DEFAULT_STAGE_SECONDS})
  AUTO_ROLLBACK   Roll back on regression: true|false (default: true)
  ENSURE_METRICS  Run create-metrics.sh first: true|false (default: true)
  PREP_FLAG       Turn flag on with off variation none: true|false (default: true)
EOF
}

for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=true ;;
    --skip-metrics) ENSURE_METRICS=false ;;
    --no-prep-flag) PREP_FLAG=false ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: ${arg}" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "${ENSURE_METRICS}" == "true" && "${DRY_RUN}" != "true" ]]; then
  "${SCRIPT_DIR}/create-metrics.sh"
fi

flag_json="$(fetch_flag)"
none_idx="$(variation_index "${flag_json}" "${BASELINE_COLOR}")"
green_idx="$(variation_index "${flag_json}" "${ROLLOUT_COLOR}")"
none_id="$(variation_id "${flag_json}" "${BASELINE_COLOR}")"

if [[ -z "${none_idx}" || -z "${green_idx}" || -z "${none_id}" ]]; then
  echo "error: could not resolve variation indices for ${BASELINE_COLOR} and ${ROLLOUT_COLOR}" >&2
  exit 1
fi

rollback_bool=false
if [[ "${AUTO_ROLLBACK}" == "true" ]]; then
  rollback_bool=true
fi

stage_ms=$((STAGE_SECONDS * 1000))
total_minutes=$((STAGE_SECONDS * ${#ROLLOUT_PERCENTAGES[@]} / 60))

targeting_json="$(jq -n \
  --argjson none_idx "${none_idx}" \
  --argjson green_idx "${green_idx}" \
  --argjson stage_ms "${stage_ms}" \
  --argjson rollback "${rollback_bool}" \
  --argjson p1 10000 \
  --argjson p2 20000 \
  --argjson p3 30000 \
  --argjson p4 50000 \
  '{
    on: true,
    offVariation: $none_idx,
    fallthrough: {
      guardedRolloutConfig: {
        randomizationUnit: "user",
        controlVariation: $none_idx,
        endVariation: $green_idx,
        stages: [
          {rolloutWeight: $p1, monitoringWindowMilliseconds: $stage_ms},
          {rolloutWeight: $p2, monitoringWindowMilliseconds: $stage_ms},
          {rolloutWeight: $p3, monitoringWindowMilliseconds: $stage_ms},
          {rolloutWeight: $p4, monitoringWindowMilliseconds: $stage_ms}
        ],
        metrics: [
          {metricKey: "grid-nav-latency", onRegression: {rollback: $rollback}},
          {metricKey: "grid-highlight-error-rate", onRegression: {rollback: $rollback}},
          {metricKey: "grid-nav-movement", onRegression: {rollback: $rollback}}
        ]
      }
    }
  }')"

targeting_file="${SCRIPT_DIR}/guarded-rollout-targeting.json"

prep_body="$(jq -n \
  --arg env "${LD_ENVIRONMENT_KEY}" \
  --arg none_id "${none_id}" \
  '{
    environmentKey: $env,
    comment: "15-guarded-rollout: prepare flag for guarded rollout UI setup",
    instructions: [
      {kind: "updateOffVariation", variationId: $none_id},
      {kind: "turnFlagOn"}
    ]
  }')"

echo "Guarded rollout preparation for ${FLAG_KEY}:"
echo "  Environment: ${LD_ENVIRONMENT_KEY}"
echo "  Fallback / baseline: ${BASELINE_COLOR} (index ${none_idx}) — no highlight"
echo "  Rollout target: ${ROLLOUT_COLOR} (index ${green_idx})"
echo "  Duration: ${total_minutes} minutes (${STAGE_SECONDS}s per stage)"
for i in "${!ROLLOUT_PERCENTAGES[@]}"; do
  start=$((i * STAGE_SECONDS / 60))
  end=$(((i + 1) * STAGE_SECONDS / 60))
  echo "    Stage $((i + 1)) (${start}:00–${end}:00): ${ROLLOUT_PERCENTAGES[$i]}% ${ROLLOUT_COLOR}"
done
echo "  Metrics:"
echo "    - ${METRIC_KEY_LATENCY}"
echo "    - ${METRIC_KEY_ERROR_RATE}"
echo "    - ${METRIC_KEY_MOVEMENT}"
echo "  Auto-rollback on regression: ${AUTO_ROLLBACK}"
echo
echo "IMPORTANT: REST cannot start guarded rollouts. Complete setup in the UI:"
echo "  1. Open Flags → ${FLAG_KEY} → ${LD_ENVIRONMENT_KEY}"
echo "  2. Default rule → Guarded rollout"
echo "  3. From: ${BASELINE_COLOR}  To: ${ROLLOUT_COLOR}  Context kind: user"
echo "  4. Stages: ${ROLLOUT_PERCENTAGES[*]}% over ${total_minutes} minutes"
echo "  5. Attach the three guardrail metrics above"
echo "  Or paste ${targeting_file} into the JSON targeting editor."
echo

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "Dry run — targeting JSON:"
  echo "${targeting_json}" | jq .
  echo
  echo "Dry run — flag prep semantic patch:"
  echo "${prep_body}" | jq .
  exit 0
fi

echo "${targeting_json}" | jq . > "${targeting_file}"
echo "Wrote ${targeting_file}"
echo

if [[ "${PREP_FLAG}" == "true" ]]; then
  echo "Preparing flag (on, off variation = ${BASELINE_COLOR})..."
  api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "${prep_body}" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on, offVariation, fallthrough}"
  echo
fi

echo "Next: configure the guarded rollout in the LaunchDarkly UI, then run:"
echo "  ./get-guarded-rollout.sh"
echo "  python3 ../15-guarded-rollout-monitor.py"
