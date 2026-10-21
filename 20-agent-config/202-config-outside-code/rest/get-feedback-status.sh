#!/usr/bin/env bash
# LaunchDarkly: AgentControl metrics — positive/negative feedback snapshot
# Multi-line status for before/after generate + thumbs demos.
# https://launchdarkly.com/docs/api/agent-control/get-ai-config-metrics
# https://launchdarkly.com/docs/home/agentcontrol/monitor
#
# Usage:
#   ./get-feedback-status.sh
#   ./get-feedback-status.sh equity-briefing-tracked-completion
#   ./get-feedback-status.sh --json
#   ./get-feedback-status.sh --verbose
#   ./get-feedback-status.sh --json --verbose
#
# Optional env:
#   LD_METRICS_LOOKBACK_HOURS  window length (default 24)
#   LD_METRICS_FROM_MS / LD_METRICS_TO_MS  override epoch millis window

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
      sed -n '2,18p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) CONFIG_KEY="$arg" ;;
  esac
done

LOOKBACK_HOURS="${LD_METRICS_LOOKBACK_HOURS:-24}"
NOW_MS="$(python3 -c 'import time; print(int(time.time() * 1000))')"
FROM_MS="${LD_METRICS_FROM_MS:-$((NOW_MS - LOOKBACK_HOURS * 3600 * 1000))}"
TO_MS="${LD_METRICS_TO_MS:-$NOW_MS}"

# UI host is the same origin as the API host (strip trailing slash).
UI_HOST="${LD_API_HOST%/}"
CONFIG_URL="${UI_HOST}/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}"
# Monitoring is a tab on the config detail page; deep-link when the SPA supports it.
MONITORING_URL="${CONFIG_URL}/monitoring"
DOCS_MONITOR="https://launchdarkly.com/docs/home/agentcontrol/monitor"
DOCS_AUTOGEN="https://launchdarkly.com/docs/home/metrics/autogen/ai"
DOCS_METRICS_API="https://launchdarkly.com/docs/api/agent-control/get-ai-config-metrics"

PATH_Q="/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/metrics?env=${LD_ENVIRONMENT_KEY}&from=${FROM_MS}&to=${TO_MS}"

RAW="$(api_ok GET "${PATH_Q}")"

if [[ "$JSON" -eq 1 ]]; then
  echo "$RAW" | jq \
    --arg cfg "$CONFIG_KEY" \
    --arg env "$LD_ENVIRONMENT_KEY" \
    --argjson from "$FROM_MS" \
    --argjson to "$TO_MS" \
    --argjson hours "$LOOKBACK_HOURS" \
    --argjson verbose "$VERBOSE" \
    --arg configUrl "$CONFIG_URL" \
    --arg monitoringUrl "$MONITORING_URL" \
    --arg docsMonitor "$DOCS_MONITOR" \
    --arg docsAutogen "$DOCS_AUTOGEN" \
    --arg docsMetricsApi "$DOCS_METRICS_API" '
    (.thumbsUp // 0) as $up
    | (.thumbsDown // 0) as $down
    | ($up + $down) as $total
    | {
        configKey: $cfg,
        environment: $env,
        lookbackHours: $hours,
        fromMs: $from,
        toMs: $to,
        positive: $up,
        negative: $down,
        total: $total,
        positiveRate: (if $total == 0 then null else ($up / $total) end),
        negativeRate: (if $total == 0 then null else ($down / $total) end),
        satisfactionRating: (.satisfactionRating // null),
        generationSuccessCount: (.generationSuccessCount // 0),
        generationErrorCount: (.generationErrorCount // 0)
      }
    | if $verbose == 1 then . + {
        links: {
          agentConfig: $configUrl,
          monitoring: $monitoringUrl,
          docsMonitor: $docsMonitor,
          docsAutogenMetrics: $docsAutogen,
          docsMetricsApi: $docsMetricsApi
        },
        events: [
          {
            key: "$ld:ai:feedback:user:positive",
            name: "Positive AI feedback (thumbs up)"
          },
          {
            key: "$ld:ai:feedback:user:negative",
            name: "Negative AI feedback (thumbs down)"
          },
          {
            key: "$ld:ai:generation:success",
            name: "AI completion success"
          },
          {
            key: "$ld:ai:generation:error",
            name: "AI completion error"
          }
        ],
        relatedAutogenMetrics: [
          {
            name: "Positive AI feedback count",
            event: "$ld:ai:feedback:user:positive"
          },
          {
            name: "Positive AI feedback rate",
            event: "$ld:ai:feedback:user:positive"
          },
          {
            name: "Negative AI feedback count",
            event: "$ld:ai:feedback:user:negative"
          },
          {
            name: "Negative AI feedback rate",
            event: "$ld:ai:feedback:user:negative"
          },
          {
            name: "AI completion success count",
            event: "$ld:ai:generation:success"
          }
        ]
      } else . end
  '
  exit 0
fi

# Multi-line human summary — labels match API / Monitoring vocabulary.
echo "$RAW" | jq -r \
  --arg cfg "$CONFIG_KEY" \
  --arg env "$LD_ENVIRONMENT_KEY" \
  --argjson hours "$LOOKBACK_HOURS" '
  (.thumbsUp // 0) as $up
  | (.thumbsDown // 0) as $down
  | ($up + $down) as $total
  | (if $total == 0 then "n/a" else (($up / $total * 100) | . * 10 | round / 10 | tostring) + "%" end) as $up_pct
  | (if $total == 0 then "n/a" else (($down / $total * 100) | . * 10 | round / 10 | tostring) + "%" end) as $down_pct
  | [
      "Agent Config Key: \($cfg)",
      "Environment: \($env)  (last \($hours)h)",
      "Thumbs Up: \($up)  (positiveRate=\($up_pct))",
      "Thumbs Down: \($down)  (negativeRate=\($down_pct))",
      "count=\($total)  (Thumbs Up + Thumbs Down)",
      "generationSuccessCount=\(.generationSuccessCount // 0)  generationErrorCount=\(.generationErrorCount // 0)"
    ]
  | .[]
'

if [[ "$VERBOSE" -eq 1 ]]; then
  cat <<EOF

Links:
  Agent Config:  ${CONFIG_URL}
  Monitoring:    ${MONITORING_URL}
                 (Satisfaction / Generations charts — pick env ${LD_ENVIRONMENT_KEY})
  Docs monitor:  ${DOCS_MONITOR}
  Docs autogen:  ${DOCS_AUTOGEN}
  Docs metrics:  ${DOCS_METRICS_API}

Event key → Event name
  \$ld:ai:feedback:user:positive  →  Positive AI feedback (thumbs up)
  \$ld:ai:feedback:user:negative  →  Negative AI feedback (thumbs down)
  \$ld:ai:generation:success      →  AI completion success
  \$ld:ai:generation:error        →  AI completion error

Related autogen metrics (Experiments / Guarded rollouts):
  Positive AI feedback count   (event: \$ld:ai:feedback:user:positive)
  Positive AI feedback rate    (event: \$ld:ai:feedback:user:positive)
  Negative AI feedback count   (event: \$ld:ai:feedback:user:negative)
  Negative AI feedback rate    (event: \$ld:ai:feedback:user:negative)
  AI completion success count  (event: \$ld:ai:generation:success)
EOF
fi

# Monitoring aggregates on a short delay (~1 min). Say so on stderr once.
echo "note: LD Monitoring can lag ~1 min after thumbs; re-run if counts look stale." >&2
