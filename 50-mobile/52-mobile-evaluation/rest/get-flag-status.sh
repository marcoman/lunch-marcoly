#!/usr/bin/env bash
# LaunchDarkly: feature-flag status snapshot (52-mobile-evaluation)
# Demo-facing check: flags exist, mobile-key availability, env on/off + variations.
# https://launchdarkly.com/docs/api/feature-flags/get-feature-flag
# https://launchdarkly.com/docs/home/flags/creating-flags#make-flags-available-to-client-side-and-mobile-sdks
# https://launchdarkly.com/docs/sdk/client-side/android
#
# Usage:
#   ./get-flag-status.sh
#   ./get-flag-status.sh show-mobile-move-count
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
FLAG_FILTER=""
for arg in "$@"; do
  case "$arg" in
    --json) JSON=1 ;;
    --verbose|-v) VERBOSE=1 ;;
    -h|--help)
      sed -n '2,16p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) FLAG_FILTER="$arg" ;;
  esac
done

UI_HOST="${LD_API_HOST%/}"
DOCS_GET="https://launchdarkly.com/docs/api/feature-flags/get-feature-flag"
DOCS_CLIENT="https://launchdarkly.com/docs/home/flags/creating-flags#make-flags-available-to-client-side-and-mobile-sdks"
DOCS_ANDROID="https://launchdarkly.com/docs/sdk/client-side/android"

EXPECTED_JSON="$(jq -nc '
  [
    {
      key: "enable-mobile-grid-highlight",
      kind: "string",
      expectedOff: "none",
      expectedFallthroughWhenOn: "green",
      requiredValues: ["none", "green", "yellow", "red", "blue", "purple"]
    },
    {
      key: "show-mobile-move-count",
      kind: "boolean",
      expectedOff: false,
      expectedFallthroughWhenOn: true,
      requiredValues: [true, false]
    }
  ]
')"

if [[ -n "$FLAG_FILTER" ]]; then
  EXPECTED_JSON="$(echo "$EXPECTED_JSON" | jq -c --arg k "$FLAG_FILTER" '
    map(select(.key == $k))
  ')"
  if [[ "$(echo "$EXPECTED_JSON" | jq 'length')" -eq 0 ]]; then
    echo "error: unknown flag key ${FLAG_FILTER}" >&2
    echo "expected: enable-mobile-grid-highlight | show-mobile-move-count" >&2
    exit 1
  fi
fi

FLAGS_JSON='[]'
while IFS= read -r expected; do
  key="$(echo "$expected" | jq -r '.key')"
  status="$(api_status GET "/flags/${LD_PROJECT_KEY}/${key}?env=${LD_ENVIRONMENT_KEY}")"
  if [[ "$status" == "200" ]]; then
    raw="$(api_ok GET "/flags/${LD_PROJECT_KEY}/${key}?env=${LD_ENVIRONMENT_KEY}")"
  else
    raw='null'
  fi
  entry="$(jq -nc \
    --argjson expected "$expected" \
    --argjson flag "$raw" \
    --argjson http "$status" \
    --arg env "$LD_ENVIRONMENT_KEY" '
    $expected as $exp
    | ($flag != null) as $found
    | ($flag.environments[$env] // null) as $e
    | ($flag.variations // []) as $vars
    | ($flag.clientSideAvailability // {}) as $csa
    | (
        ($e.offVariation | if type == "number" then $vars[.].value else null end)
      ) as $off_val
    | (
        ($e.fallthrough.variation // $e.fallthrough // null) as $ft
        | if ($ft | type) == "number" then ($vars[$ft].value // null)
          else null end
      ) as $ft_val
    | ($vars | map(.value)) as $values
    | (
        ($exp.requiredValues | map(. as $need | ($values | index($need) != null)) | all)
      ) as $values_ok
    | ($csa.usingMobileKey == true) as $mobile_ok
    | {
        key: $exp.key,
        kind: $exp.kind,
        found: $found,
        httpStatus: $http,
        name: ($flag.name // null),
        clientSideAvailability: $csa,
        usingEnvironmentId: ($csa.usingEnvironmentId // false),
        usingMobileKey: ($csa.usingMobileKey // false),
        mobileMatches: $mobile_ok,
        valuesPresent: $values_ok,
        variations: ($vars | map({value, name})),
        targeting: {
          on: (if $e == null then null else ($e.on == true) end),
          offVariation: $off_val,
          fallthrough: $ft_val,
          expectedOff: $exp.expectedOff,
          expectedFallthroughWhenOn: $exp.expectedFallthroughWhenOn,
          offMatches: ($off_val == $exp.expectedOff)
        },
        healthy: ($found and $mobile_ok and $values_ok)
      }
  ')"
  FLAGS_JSON="$(jq -c --argjson e "$entry" '. + [$e]' <<<"$FLAGS_JSON")"
done < <(echo "$EXPECTED_JSON" | jq -c '.[]')

STATUS_JSON="$(jq -nc \
  --arg project "$LD_PROJECT_KEY" \
  --arg env "$LD_ENVIRONMENT_KEY" \
  --argjson flags "$FLAGS_JSON" \
  --argjson verbose "$VERBOSE" \
  --arg docsGet "$DOCS_GET" \
  --arg docsClient "$DOCS_CLIENT" \
  --arg docsAndroid "$DOCS_ANDROID" \
  --arg uiHost "$UI_HOST" '
  {
    projectKey: $project,
    environment: $env,
    healthy: ([$flags[].healthy] | all),
    flags: $flags
  }
  | if $verbose == 1 then . + {
      links: {
        flags: ($flags | map({
          key: .key,
          flag: "\($uiHost)/projects/\($project)/flags/\(.key)"
        })),
        docsGetFlag: $docsGet,
        docsClientSideAvailability: $docsClient,
        docsAndroidSdk: $docsAndroid
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
      "Healthy: \(if .healthy then "yes" else "NO — check exists / mobile-key availability / variations" end)",
      "",
      "Flags:",
      (.flags[] |
        "  \(if .healthy then "✓" else "✗" end) \(.key)"
        + "  mobile-key=\(if .usingMobileKey then "yes" else "NO" end)"
        + "  on=\(.targeting.on | if . == null then "n/a" else tostring end)"
        + "  off=\(.targeting.offVariation | tostring)"
        + "  fallthrough=\(.targeting.fallthrough | tostring)"
        + (if .found then "" else "  (missing HTTP \(.httpStatus))" end)
        + (if .found and (.mobileMatches|not) then "  (enable usingMobileKey)" else "" end)
        + (if .found and (.valuesPresent|not) then "  (variations incomplete)" else "" end)
      )
    ]
  | .[]
'

if [[ "$VERBOSE" -eq 1 ]]; then
  cat <<EOF

Expected (after ./create-flags.sh):
  enable-mobile-grid-highlight  string  mobile SDK  off=none  fallthrough=green
  show-mobile-move-count        boolean mobile SDK  off=false fallthrough=true

Links:
EOF
  echo "$STATUS_JSON" | jq -r '.links.flags[]? | "  \(.key): \(.flag)"'
  cat <<EOF
  Docs get flag:     ${DOCS_GET}
  Docs availability: ${DOCS_CLIENT}
  Docs Android SDK:  ${DOCS_ANDROID}

If Healthy=NO and flags are missing: ./create-flags.sh
If mobile-key=NO: turn on "SDKs using Mobile key" on each flag (create-flags.sh sets this).
EOF
fi
