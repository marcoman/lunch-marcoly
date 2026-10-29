#!/usr/bin/env bash
# Start a progressive environment release on a new targeting rule.
#
# One phase, five steps: 10%, 20%, 40%, 60%, 100%. No metrics, so the
# release kind is progressive. The default rule is not a valid target.
# The phase clause matches every user context.
#
# LaunchDarkly: start an environment release
# https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

STAGE_SECONDS="${STAGE_SECONDS:-${DEFAULT_STAGE_SECONDS}}"
BYPASS_HEALTH=false
PREP_FLAG=true

usage() {
  cat <<EOF
usage: $0 [--bypass-health-checks] [--no-prep]

Start a progressive environment release for ${FLAG_KEY}.

The flag must be on. By default this script turns it on and sets the
default rule to ${BASELINE_COLOR} before the POST. Log in on the grid
once first so the flag has a recent user evaluation. Health checks
reject a flag with no recent evaluations unless you pass
--bypass-health-checks.

Options:
  --bypass-health-checks  Start even if flag-evaluation health checks fail
  --no-prep               Do not turn the flag on or set the default rule

Environment:
  STAGE_SECONDS   Seconds for each step (default: ${DEFAULT_STAGE_SECONDS})
EOF
}

for arg in "$@"; do
  case "${arg}" in
    --bypass-health-checks) BYPASS_HEALTH=true ;;
    --no-prep) PREP_FLAG=false ;;
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

if ! [[ "${STAGE_SECONDS}" =~ ^[0-9]+$ ]] || [[ "${STAGE_SECONDS}" -lt 1 ]]; then
  echo "error: STAGE_SECONDS must be a positive integer" >&2
  exit 1
fi

flag_json="$(fetch_flag)"
none_id="$(variation_id "${flag_json}" "${BASELINE_COLOR}")"
green_id="$(variation_id "${flag_json}" "${ROLLOUT_COLOR}")"
if [[ -z "${none_id}" || -z "${green_id}" || "${none_id}" == "null" || "${green_id}" == "null" ]]; then
  echo "error: could not resolve variation ids for ${BASELINE_COLOR} and ${ROLLOUT_COLOR}" >&2
  echo "Run ./create-flag.sh first." >&2
  exit 1
fi

if [[ "${PREP_FLAG}" == "true" ]]; then
  echo "Turning ${FLAG_KEY} on. Default rule serves ${BASELINE_COLOR}."
  api PATCH "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "$(jq -n --arg env "${LD_ENVIRONMENT_KEY}" --arg none "${none_id}" '{
      environmentKey: $env,
      comment: "22-api-progressive-rollout: on, default rule stays none",
      instructions: [
        {kind: "turnFlagOn"},
        {kind: "updateFallthroughVariationOrRollout", variationId: $none}
      ]
    }')" >/dev/null
fi

duration_ms=$((STAGE_SECONDS * 1000))
steps="$(printf '%s\n' "${ROLLOUT_PERCENTAGES[@]}" | jq -s --argjson ms "${duration_ms}" \
  '[.[] | {allocation: (. * 1000), durationMillis: $ms}]')"

body="$(jq -n \
  --arg none "${none_id}" \
  --arg green "${green_id}" \
  --arg unit "${RANDOMIZATION_UNIT}" \
  --argjson steps "${steps}" \
  --argjson bypass "${BYPASS_HEALTH}" \
  '{
    originalVariationId: $none,
    targetVariationId: $green,
    randomizationUnit: $unit,
    cleanupBehavior: "remove_rules_and_update_default_rule",
    comment: "22-api-progressive-rollout: start progressive release",
    phases: [
      {
        description: "All users",
        clauses: [
          {
            contextKind: $unit,
            attribute: "kind",
            op: "in",
            values: [$unit]
          }
        ],
        steps: $steps
      }
    ]
  }
  + (if $bypass then {bypassHealthChecks: ["flag_evaluations_any", "flag_evaluations_with_context"]} else {} end)')"

echo "Starting progressive release (${ROLLOUT_PERCENTAGES[*]}% , ${STAGE_SECONDS}s each)..."
if ! response="$(api_beta POST "$(releases_path)" \
  -H "Content-Type: application/json" \
  -d "${body}")"; then
  echo "If that was health_checks_failed, open the grid and log in once, then retry." >&2
  echo "A lab with no traffic yet can pass --bypass-health-checks." >&2
  exit 1
fi

echo "${response}" | jq '{
  id,
  kind,
  status,
  statusReason,
  randomizationUnit,
  metricCount: (.metrics | length),
  cleanupBehavior,
  ruleId: .phases[0].ruleId,
  steps: [.phases[0].steps[] | {percent: (.allocation / 1000), durationSeconds: (.durationMillis / 1000)}]
}'
echo "Next: ./get-progressive-release.sh"
