#!/usr/bin/env bash
# LaunchDarkly: AgentControl tools status snapshot (23-agent-tools)
# Demo-facing check: Library tools exist, variation has them attached,
# targeting is on, and generation metrics moved after Generate.
# https://launchdarkly.com/docs/home/agentcontrol/tools
# https://launchdarkly.com/docs/home/agentcontrol/monitor
# https://launchdarkly.com/docs/api/agent-control/get-ai-config
# https://launchdarkly.com/docs/api/agent-control/get-ai-config-metrics
#
# Usage:
#   ./get-tools-status.sh
#   ./get-tools-status.sh equity-briefing-tools
#   ./get-tools-status.sh --json
#   ./get-tools-status.sh --verbose
#   ./get-tools-status.sh --json --verbose
#
# Optional env:
#   LD_METRICS_LOOKBACK_HOURS  window length (default 24)
#   LD_METRICS_FROM_MS / LD_METRICS_TO_MS  override epoch millis window
#   LD_VARIATION_KEY          variation to inspect (default tools-anthropic)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

JSON=0
VERBOSE=0
CONFIG_KEY="${LD_CONFIG_KEY}"
for arg in "$@"; do
  case "$arg" in
    --json) JSON=1 ;;
    --verbose|-v) VERBOSE=1 ;;
    -h|--help)
      sed -n '2,22p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) CONFIG_KEY="$arg" ;;
  esac
done

LOOKBACK_HOURS="${LD_METRICS_LOOKBACK_HOURS:-24}"
NOW_MS="$(python3 -c 'import time; print(int(time.time() * 1000))')"
FROM_MS="${LD_METRICS_FROM_MS:-$((NOW_MS - LOOKBACK_HOURS * 3600 * 1000))}"
TO_MS="${LD_METRICS_TO_MS:-$NOW_MS}"

UI_HOST="${LD_API_HOST%/}"
CONFIG_URL="${UI_HOST}/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}"
MONITORING_URL="${CONFIG_URL}/monitoring"
TOOLS_LIBRARY_URL="${UI_HOST}/projects/${LD_PROJECT_KEY}/ai-tools"
DOCS_TOOLS="https://launchdarkly.com/docs/home/agentcontrol/tools"
DOCS_MONITOR="https://launchdarkly.com/docs/home/agentcontrol/monitor"
DOCS_METRICS_API="https://launchdarkly.com/docs/api/agent-control/get-ai-config-metrics"

EXPECTED_TOOLS=("${LD_TOOL_ANALYZE_KEY}" "${LD_TOOL_COMPARE_KEY}")

# --- Library: each expected tool key ---
LIBRARY_JSON='[]'
for tool_key in "${EXPECTED_TOOLS[@]}"; do
  status="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-tools/${tool_key}")"
  if [[ "$status" == "200" ]]; then
    entry="$(api GET "/projects/${LD_PROJECT_KEY}/ai-tools/${tool_key}" \
      | jq -c --arg key "$tool_key" '{key: $key, exists: true, version: (.version // null), description: (.description // null)}')"
  else
    entry="$(jq -nc --arg key "$tool_key" --argjson http "$status" \
      '{key: $key, exists: false, httpStatus: $http}')"
  fi
  LIBRARY_JSON="$(jq -c --argjson e "$entry" '. + [$e]' <<<"$LIBRARY_JSON")"
done

# --- Config + variation tools ---
CONFIG_RAW="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}")"
VARIATION_KEY="${LD_VARIATION_KEY}"

CONFIG_SUMMARY="$(echo "$CONFIG_RAW" | jq -c \
  --arg vkey "$VARIATION_KEY" \
  --argjson expected "$(printf '%s\n' "${EXPECTED_TOOLS[@]}" | jq -R . | jq -s .)" '
  (.variations // []) as $vars
  | ($vars | map(select(.key == $vkey)) | .[0]) as $var
  | ($var.tools // [] | map(.key // .) | map(tostring)) as $attached
  | ($expected | map(. as $t | {
      key: $t,
      attached: ($attached | index($t) != null)
    })) as $checks
  | {
      key: .key,
      name: .name,
      mode: .mode,
      variationKey: $vkey,
      variationFound: ($var != null),
      variationName: ($var.name // null),
      modelName: ($var.model.modelName // $var.modelConfigKey // null),
      attachedToolKeys: $attached,
      expectedTools: $checks,
      allExpectedAttached: ([$checks[].attached] | all),
      messageRoles: ([($var.messages // [])[]?.role] | unique)
    }
')"

# --- Targeting ---
TARGET_RAW="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/targeting?env=${LD_ENVIRONMENT_KEY}")"
TARGET_SUMMARY="$(echo "$TARGET_RAW" | jq -c \
  --arg env "$LD_ENVIRONMENT_KEY" \
  --arg vkey "$VARIATION_KEY" '
  (.environments[$env] // null) as $e
  | (.variations // []) as $vars
  | ($e.fallthrough.variation // $e.fallthrough // null) as $ft
  | (if ($ft | type) == "number" then ($vars[$ft].key // null)
     elif ($ft | type) == "string" then $ft
     elif ($ft | type) == "object" then ($ft.variation // $ft.key // null)
     else null end) as $ft_key
  | {
      environment: $env,
      on: ($e.on // null),
      fallthroughVariation: $ft_key,
      fallthroughMatchesExpected: ($ft_key == $vkey),
      offVariation: ($e.offVariation // null)
    }
')"

# --- Metrics (generations; tool-call counts are Monitoring UI / track_tool_call) ---
METRICS_PATH="/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/metrics?env=${LD_ENVIRONMENT_KEY}&from=${FROM_MS}&to=${TO_MS}"
METRICS_RAW="$(api_ok GET "${METRICS_PATH}")"
METRICS_SUMMARY="$(echo "$METRICS_RAW" | jq -c \
  --argjson hours "$LOOKBACK_HOURS" \
  --argjson from "$FROM_MS" \
  --argjson to "$TO_MS" '
  {
    lookbackHours: $hours,
    fromMs: $from,
    toMs: $to,
    generationSuccessCount: (.generationSuccessCount // 0),
    generationErrorCount: (.generationErrorCount // 0),
    inputTokens: (.inputTokens // null),
    outputTokens: (.outputTokens // null),
    totalTokens: (.totalTokens // null),
    note: "Per-tool call counts from track_tool_call appear on the Monitoring tab; this metrics endpoint does not break them out by tool key."
  }
')"

STATUS_JSON="$(jq -nc \
  --arg cfg "$CONFIG_KEY" \
  --arg env "$LD_ENVIRONMENT_KEY" \
  --argjson library "$LIBRARY_JSON" \
  --argjson config "$CONFIG_SUMMARY" \
  --argjson targeting "$TARGET_SUMMARY" \
  --argjson metrics "$METRICS_SUMMARY" \
  --argjson verbose "$VERBOSE" \
  --arg configUrl "$CONFIG_URL" \
  --arg monitoringUrl "$MONITORING_URL" \
  --arg toolsLibraryUrl "$TOOLS_LIBRARY_URL" \
  --arg docsTools "$DOCS_TOOLS" \
  --arg docsMonitor "$DOCS_MONITOR" \
  --arg docsMetricsApi "$DOCS_METRICS_API" '
  ($library | map(.exists) | all) as $lib_ok
  | ($config.allExpectedAttached) as $attach_ok
  | {
      configKey: $cfg,
      environment: $env,
      healthy: ($lib_ok and $attach_ok and ($config.variationFound == true)),
      library: $library,
      config: $config,
      targeting: $targeting,
      metrics: $metrics
    }
  | if $verbose == 1 then . + {
      links: {
        agentConfig: $configUrl,
        monitoring: $monitoringUrl,
        toolsLibrary: $toolsLibraryUrl,
        docsTools: $docsTools,
        docsMonitor: $docsMonitor,
        docsMetricsApi: $docsMetricsApi
      },
      events: [
        { key: "$ld:ai:generation:success", name: "AI completion success" },
        { key: "$ld:ai:generation:error", name: "AI completion error" },
        { key: "track_tool_call", name: "Tool invocations (Monitoring; SDK tracker)" }
      ]
    } else . end
')"

if [[ "$JSON" -eq 1 ]]; then
  echo "$STATUS_JSON" | jq .
  exit 0
fi

# Multi-line human summary
echo "$STATUS_JSON" | jq -r '
  . as $s
  | [
      "Agent Config Key: \(.configKey)",
      "Environment: \(.environment)  (last \(.metrics.lookbackHours)h)",
      "Healthy: \(if .healthy then "yes" else "NO — check Library / attach / variation" end)",
      "",
      "Library tools:",
      (.library[] | "  \(if .exists then "✓" else "✗" end) \(.key)\(if .exists then "  (v\(.version // "?"))" else "  (missing)" end)"),
      "",
      "Variation \(.config.variationKey):",
      "  found=\(.config.variationFound)  model=\(.config.modelName // "n/a")",
      "  attached: \((.config.attachedToolKeys // []) | join(", "))",
      (.config.expectedTools[] | "  \(if .attached then "✓" else "✗" end) \(.key)"),
      "",
      "Targeting:",
      "  on=\(.targeting.on)  fallthrough=\(.targeting.fallthroughVariation // "n/a")\(if .targeting.fallthroughMatchesExpected then " (matches)" else " (expected \(.config.variationKey))" end)",
      "",
      "Metrics (last \(.metrics.lookbackHours)h):",
      "  generationSuccessCount=\(.metrics.generationSuccessCount)  generationErrorCount=\(.metrics.generationErrorCount)",
      (if .metrics.totalTokens != null then "  tokens total=\(.metrics.totalTokens)  (in=\(.metrics.inputTokens // "n/a") out=\(.metrics.outputTokens // "n/a"))" else empty end)
    ]
  | .[]
'

if [[ "$VERBOSE" -eq 1 ]]; then
  cat <<EOF

Links:
  Agent Config:   ${CONFIG_URL}
  Monitoring:     ${MONITORING_URL}
                  (Generations + tool usage — pick env ${LD_ENVIRONMENT_KEY})
  Tools Library:  ${TOOLS_LIBRARY_URL}
  Docs tools:     ${DOCS_TOOLS}
  Docs monitor:   ${DOCS_MONITOR}
  Docs metrics:   ${DOCS_METRICS_API}

Events / tracking:
  \$ld:ai:generation:success  →  AI completion success
  \$ld:ai:generation:error    →  AI completion error
  tracker.track_tool_call()  →  per-tool usage on Monitoring (not in metrics JSON)

Note: this example does not collect thumbs feedback (see 22 get-feedback-status.sh).
EOF
fi

echo "note: LD Monitoring can lag ~1 min after Generate / tool calls; re-run if counts look stale." >&2
echo "note: per-tool counts live on the Monitoring tab — metrics API has generations/tokens only." >&2
