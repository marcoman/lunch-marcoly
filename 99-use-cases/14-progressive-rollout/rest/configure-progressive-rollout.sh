#!/usr/bin/env bash
# Prepare progressive-rollout targeting JSON for the LaunchDarkly UI.
#
# In this example, we have a progressive rollout over 15 minutes in five equal
# stages: 10%, 20%, 40%, 60%, and 100% of users receive the green highlight.
#
# NOTE: LaunchDarkly's public REST semantic-patch API does not start progressive
# rollouts — progressiveRolloutConfig is ignored on updateFallthroughVariationOrRollout.
# Use start-progressive-rollout.sh to simulate stage timing via REST percentage
# updates, or complete setup in the UI (Default rule → Progressive rollout).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

STAGE_MINUTES="${STAGE_MINUTES:-$((DEFAULT_STAGE_SECONDS / 60))}"
PREP_FLAG="${PREP_FLAG:-true}"
DRY_RUN=false

usage() {
  cat <<EOF
usage: $0 [--dry-run] [--no-prep-flag]

Prepare progressive-rollout targeting JSON for ${FLAG_KEY}.

This script does NOT start a UI progressive rollout via REST. After it runs:
  - ./start-progressive-rollout.sh simulates stage timing with REST percentages, or
  - configure Default rule → Progressive rollout in the LaunchDarkly UI.

Options:
  --dry-run       Print actions without applying them
  --no-prep-flag  Do not turn the flag on or set off variation to none

Environment overrides:
  STAGE_MINUTES   Minutes per stage (default: ${STAGE_MINUTES})
  PREP_FLAG       Turn flag on with off variation none: true|false (default: true)
EOF
}

for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=true ;;
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

flag_json="$(fetch_flag)"
none_idx="$(variation_index "${flag_json}" "${BASELINE_COLOR}")"
green_idx="$(variation_index "${flag_json}" "${ROLLOUT_COLOR}")"
none_id="$(variation_id "${flag_json}" "${BASELINE_COLOR}")"

if [[ -z "${none_idx}" || -z "${green_idx}" || -z "${none_id}" ]]; then
  echo "error: could not resolve variation indices for ${BASELINE_COLOR} and ${ROLLOUT_COLOR}" >&2
  exit 1
fi

total_minutes=$((STAGE_MINUTES * ${#ROLLOUT_PERCENTAGES[@]}))

targeting_json="$(jq -n \
  --argjson none_idx "${none_idx}" \
  --argjson green_idx "${green_idx}" \
  --argjson stage_minutes "${STAGE_MINUTES}" \
  --argjson p1 10000 \
  --argjson p2 20000 \
  --argjson p3 40000 \
  --argjson p4 60000 \
  --argjson p5 100000 \
  '{
    on: true,
    offVariation: $none_idx,
    fallthrough: {
      progressiveRolloutConfig: {
        contextKind: "user",
        controlVariation: $none_idx,
        endVariation: $green_idx,
        steps: [
          {rolloutWeight: $p1, duration: {quantity: $stage_minutes, unit: "minute"}},
          {rolloutWeight: $p2, duration: {quantity: $stage_minutes, unit: "minute"}},
          {rolloutWeight: $p3, duration: {quantity: $stage_minutes, unit: "minute"}},
          {rolloutWeight: $p4, duration: {quantity: $stage_minutes, unit: "minute"}},
          {rolloutWeight: $p5, duration: {quantity: $stage_minutes, unit: "minute"}}
        ]
      }
    }
  }')"

prep_body="$(jq -n \
  --arg env "${LD_ENVIRONMENT_KEY}" \
  --arg none_id "${none_id}" \
  '{
    environmentKey: $env,
    comment: "14-progressive-rollout: prepare flag for progressive rollout UI setup",
    instructions: [
      {kind: "updateOffVariation", variationId: $none_id},
      {kind: "turnFlagOn"}
    ]
  }')"

targeting_file="${SCRIPT_DIR}/progressive-rollout-targeting.json"

echo "Progressive rollout preparation for ${FLAG_KEY}:"
echo "  Environment: ${LD_ENVIRONMENT_KEY}"
echo "  From: ${BASELINE_COLOR} (index ${none_idx}) → ${ROLLOUT_COLOR} (index ${green_idx})"
echo "  Duration: ${total_minutes} minutes (${STAGE_MINUTES} min per stage)"
for i in "${!ROLLOUT_PERCENTAGES[@]}"; do
  start=$((i * STAGE_MINUTES))
  end=$(((i + 1) * STAGE_MINUTES))
  echo "    Stage $((i + 1)) (${start}:00–${end}:00): ${ROLLOUT_PERCENTAGES[$i]}% ${ROLLOUT_COLOR}"
done
echo
echo "IMPORTANT: REST cannot start UI progressive rollouts. Options:"
echo "  1. UI: Default rule → Progressive rollout (or paste ${targeting_file})"
echo "  2. REST simulation: ./start-progressive-rollout.sh"
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

echo "Next: ./start-progressive-rollout.sh  OR  configure progressive rollout in the UI"
echo "Verify: ./get-progressive-rollout.sh"
