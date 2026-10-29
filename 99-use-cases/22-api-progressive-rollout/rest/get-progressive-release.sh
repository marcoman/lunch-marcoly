#!/usr/bin/env bash
# Show the newest progressive environment releases for this flag.
#
# LaunchDarkly: list environment releases
# https://launchdarkly.com/docs/api/environment-releases-beta/list-environment-releases

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

LIMIT="${1:-5}"
query="queryfilter=kind%3Aequals%3Aprogressive&limit=${LIMIT}"

response="$(api_beta GET "$(releases_path)?${query}")"
echo "${response}" | jq '{
  totalCount,
  items: [.items[] | {
    id,
    kind,
    status,
    statusReason,
    randomizationUnit,
    metricCount: (.metrics | length),
    currentStepIndex: .phases[0].currentStepIndex,
    currentPercent: (
      .phases[0].steps[.phases[0].currentStepIndex // 0].allocation // null
      | if . == null then null else . / 1000 end
    ),
    hasRule: (.phases[0].ruleId != null),
    steps: [.phases[0].steps[] | {percent: (.allocation / 1000), seconds: (.durationMillis / 1000)}]
  }]
}'
