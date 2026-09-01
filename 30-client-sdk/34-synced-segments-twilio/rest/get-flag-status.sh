#!/usr/bin/env bash
# Snapshot: inner-circle flag + segment (34-synced-segments-twilio).
# https://launchdarkly.com/docs/api/feature-flags/get-feature-flag
# https://launchdarkly.com/docs/api/segments/get-segment
#
# Usage:
#   ./get-flag-status.sh
#   ./get-flag-status.sh --json
#   ./get-flag-status.sh --verbose

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

JSON=0
VERBOSE=0
for arg in "$@"; do
  case "$arg" in
    --json) JSON=1 ;;
    --verbose|-v) VERBOSE=1 ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
  esac
done

FLAG_KEY="show-twilio-inner-circle-badge"
SEGMENT_KEY="${LD_TWILIO_SEGMENT_KEY:-marcoly-twilio-inner-circle}"
DOCS_SEG="https://launchdarkly.com/docs/home/flags/twilio"
DOCS_API="https://launchdarkly.com/docs/home/flags/synced-segments"

flag_http="$(api_status GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}?env=${LD_ENVIRONMENT_KEY}")"
if [[ "$flag_http" == "200" ]]; then
  FLAG_RAW="$(api_ok GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}?env=${LD_ENVIRONMENT_KEY}")"
else
  FLAG_RAW="null"
fi

seg_http="$(api_status GET "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${SEGMENT_KEY}")"
if [[ "$seg_http" == "200" ]]; then
  SEG_RAW="$(api_ok GET "/segments/${LD_PROJECT_KEY}/${LD_ENVIRONMENT_KEY}/${SEGMENT_KEY}")"
else
  SEG_RAW="null"
fi

STATUS_JSON="$(jq -nc \
  --arg project "$LD_PROJECT_KEY" \
  --arg env "$LD_ENVIRONMENT_KEY" \
  --arg flagKey "$FLAG_KEY" \
  --arg segKey "$SEGMENT_KEY" \
  --argjson flag "$FLAG_RAW" \
  --argjson seg "$SEG_RAW" \
  --argjson flagHttp "$flag_http" \
  --argjson segHttp "$seg_http" \
  --argjson verbose "$VERBOSE" \
  --arg docsSeg "$DOCS_SEG" \
  --arg docsApi "$DOCS_API" \
  --arg uiHost "${LD_API_HOST%/}" '
  ($flag != null) as $flag_found
  | ($seg != null) as $seg_found
  | ($flag.environments[$env] // null) as $e
  | ($flag.clientSideAvailability.usingEnvironmentId == true) as $client_ok
  | (($e.rules // []) | map(.clauses[]? | select(.op == "segmentMatch") | .values[]?) | index($segKey) != null) as $has_rule
  | {
      projectKey: $project,
      environment: $env,
      healthy: ($flag_found and $seg_found and $client_ok and ($e.on == true) and $has_rule),
      flag: {
        key: $flagKey,
        found: $flag_found,
        httpStatus: $flagHttp,
        usingEnvironmentId: ($flag.clientSideAvailability.usingEnvironmentId // false),
        on: (if $e == null then null else ($e.on == true) end),
        hasSegmentRule: $has_rule
      },
      segment: {
        key: $segKey,
        found: $seg_found,
        httpStatus: $segHttp,
        unbounded: ($seg.unbounded // false),
        name: ($seg.name // null)
      }
    }
  | if $verbose == 1 then . + {
      links: {
        flag: "\($uiHost)/projects/\($project)/flags/\($flagKey)",
        docsSyncedSegments: $docsApi,
        docsTwilioAudiences: $docsSeg
      }
    } else . end
')"

if [[ "$JSON" -eq 1 ]]; then
  echo "$STATUS_JSON" | jq .
  exit 0
fi

echo "$STATUS_JSON" | jq -r '
  [
    "Project: \(.projectKey)",
    "Environment: \(.environment)",
    "Healthy: \(if .healthy then "yes" else "NO — check flag / segment / client-side / on / segmentMatch rule" end)",
    "",
    "Flag \(.flag.key):",
    "  \(if .flag.found then "✓" else "✗" end) found  client-side=\(if .flag.usingEnvironmentId then "yes" else "NO" end)  on=\(.flag.on | tostring)  segmentRule=\(if .flag.hasSegmentRule then "yes" else "NO" end)",
    "",
    "Segment \(.segment.key):",
    "  \(if .segment.found then "✓" else "✗" end) found  unbounded=\(.segment.unbounded | tostring)"
  ] | .[]
'

if [[ "$VERBOSE" -eq 1 ]]; then
  cat <<EOF

If Healthy=NO: ./create-flags.sh (flag) + Twilio Audiences sync (segment)
Membership:    Join inner circle in the app (Twilio Segment identify + track)
Docs Twilio:   ${DOCS_SEG}
Docs synced:   ${DOCS_API}
EOF
fi
