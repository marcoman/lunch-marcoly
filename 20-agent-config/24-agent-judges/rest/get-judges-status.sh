#!/usr/bin/env bash
# LaunchDarkly: AgentControl judges status snapshot (24-agent-judges)
# Demo-facing check: both custom judges exist, completion config + targeting,
# and generation metrics moved after Generate (gate / rewrite).
# https://launchdarkly.com/docs/home/agentcontrol/judges
# https://launchdarkly.com/docs/home/agentcontrol/online-evaluations
# https://launchdarkly.com/docs/home/agentcontrol/monitor
# https://launchdarkly.com/docs/api/agent-control/get-ai-config
# https://launchdarkly.com/docs/api/agent-control/get-ai-config-metrics
#
# Usage:
#   ./get-judges-status.sh
#   ./get-judges-status.sh equity-briefing-judged
#   ./get-judges-status.sh --json
#   ./get-judges-status.sh --verbose
#   ./get-judges-status.sh --json --verbose
#
# Optional env:
#   LD_METRICS_LOOKBACK_HOURS  window length (default 24; set 0 to skip metrics)
#   LD_METRICS_FROM_MS / LD_METRICS_TO_MS  override epoch millis window
#   LD_JUDGE_FIDELITY_KEY / LD_JUDGE_DISCIPLINE_KEY  override judge config keys

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
      sed -n '2,24p' "$0" | sed 's/^# \?//'
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
FIDELITY_URL="${UI_HOST}/projects/${LD_PROJECT_KEY}/ai-configs/${LD_JUDGE_FIDELITY_KEY}"
DISCIPLINE_URL="${UI_HOST}/projects/${LD_PROJECT_KEY}/ai-configs/${LD_JUDGE_DISCIPLINE_KEY}"
JUDGES_TAB_URL="${UI_HOST}/projects/${LD_PROJECT_KEY}/ai-configs?tab=judges"
DOCS_JUDGES="https://launchdarkly.com/docs/home/agentcontrol/judges"
DOCS_ONLINE="https://launchdarkly.com/docs/home/agentcontrol/online-evaluations"
DOCS_MONITOR="https://launchdarkly.com/docs/home/agentcontrol/monitor"
DOCS_METRICS_API="https://launchdarkly.com/docs/api/agent-control/get-ai-config-metrics"

# --- Judges library (mode=judge configs) ---
fetch_judge() {
  local key="$1"
  local expected_metric="$2"
  local status
  status="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${key}")"
  if [[ "$status" != "200" ]]; then
    jq -nc --arg key "$key" --argjson http "$status" --arg metric "$expected_metric" \
      '{key: $key, exists: false, httpStatus: $http, expectedEvaluationMetricKey: $metric}'
    return 0
  fi
  api GET "/projects/${LD_PROJECT_KEY}/ai-configs/${key}" | jq -c \
    --arg key "$key" \
    --arg expected "$expected_metric" '
    {
      key: $key,
      exists: true,
      name: (.name // null),
      mode: (.mode // null),
      evaluationMetricKey: (.evaluationMetricKey // null),
      expectedEvaluationMetricKey: $expected,
      metricMatches: ((.evaluationMetricKey // "") == $expected),
      isInverted: (.isInverted // null),
      variationKeys: [(.variations // [])[]?.key],
      modelHint: (
        (.variations // [])[0].model.modelName
        // (.variations // [])[0].modelConfigKey
        // null
      )
    }
  '
}

JUDGES_JSON="$(jq -nc \
  --argjson f "$(fetch_judge "$LD_JUDGE_FIDELITY_KEY" "$LD_JUDGE_FIDELITY_METRIC")" \
  --argjson d "$(fetch_judge "$LD_JUDGE_DISCIPLINE_KEY" "$LD_JUDGE_DISCIPLINE_METRIC")" \
  '[$f, $d]')"

# --- Completion config ---
CONFIG_STATUS="$(api_status GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}")"
if [[ "$CONFIG_STATUS" != "200" ]]; then
  echo "error: completion config ${CONFIG_KEY} not found (HTTP ${CONFIG_STATUS})" >&2
  echo "  Run: ./create-config.sh" >&2
  exit 1
fi

CONFIG_RAW="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}")"
CONFIG_SUMMARY="$(echo "$CONFIG_RAW" | jq -c '
  (.variations // []) as $vars
  | ($vars | map(.key)) as $keys
  | {
      key: .key,
      name: .name,
      mode: .mode,
      variationKeys: $keys,
      hasReckless: ($keys | index("reckless-hype") != null),
      hasSkeptic: ($keys | index("concise-skeptic") != null),
      variations: [
        $vars[] | {
          key,
          name,
          modelConfigKey,
          modelName: (.model.modelName // null)
        }
      ]
    }
')"

# --- Targeting (Toby / Charlie) ---
TARGET_RAW="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/targeting?env=${LD_ENVIRONMENT_KEY}")"
TARGET_SUMMARY="$(echo "$TARGET_RAW" | jq -c \
  --arg env "$LD_ENVIRONMENT_KEY" '
  (.environments[$env] // null) as $e
  | (.variations // []) as $tvars
  | ($e.fallthrough.variation // $e.fallthrough // null) as $ft_raw
  | (
      if ($ft_raw | type) == "number" then ($tvars[$ft_raw].key // $tvars[$ft_raw].name // null)
      elif ($ft_raw | type) == "string" then
        ( ($tvars | map(select(._id == $ft_raw or .key == $ft_raw or .name == $ft_raw)) | .[0].key // .[0].name)
          // $ft_raw )
      elif ($ft_raw | type) == "object" then
        ( $ft_raw.variation
          | if type == "number" then ($tvars[.].key // $tvars[.].name // null)
            elif type == "string" then
              ( ($tvars | map(select(._id == . or .key == . or .name == .)) | .[0].key // .[0].name) // . )
            else null end )
      else null end
    ) as $ft_key
  | (
      ($e.rules // [])
      | map(
          . as $rule
          | (
              if ($rule.variation | type) == "number" then ($tvars[$rule.variation].key // $tvars[$rule.variation].name // null)
              elif ($rule.variationId | type) == "string" then
                ($tvars | map(select(._id == $rule.variationId)) | .[0].key // .[0].name // null)
              elif ($rule.variation | type) == "string" then
                ($tvars | map(select(._id == $rule.variation or .key == $rule.variation or .name == $rule.variation)) | .[0].key // .[0].name // $rule.variation)
              else null end
            ) as $vkey
          | ($rule.clauses // []) as $clauses
          | ($clauses | map(select((.attribute // "") == "name")) | .[0]) as $name_clause
          | {
              description: ($rule.description // null),
              variationKey: $vkey,
              names: ($name_clause.values // [])
            }
        )
    ) as $rules
  | {
      environment: $env,
      on: ($e.on // null),
      fallthroughVariation: $ft_key,
      fallthroughIsSkeptic: ($ft_key == "concise-skeptic"),
      offVariation: ($e.offVariation // null),
      nameRules: $rules,
      charlieToSkeptic: (
        [$rules[] | select(.names | index("Conservative Charlie")) | .variationKey]
        | .[0] == "concise-skeptic"
      ),
      tobyToReckless: (
        [$rules[] | select(.names | index("Thoughtless Toby")) | .variationKey]
        | .[0] == "reckless-hype"
      )
    }
')"

# --- Metrics (completion config generations) ---
METRICS_SUMMARY='null'
if [[ "$LOOKBACK_HOURS" != "0" ]]; then
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
      note: "Judge scores ($ld:ai:judge:…) appear on Monitoring / Judge metrics; this snapshot focuses on completion generations after the gate demo."
    }
  ')"
fi

STATUS_JSON="$(jq -nc \
  --arg cfg "$CONFIG_KEY" \
  --arg env "$LD_ENVIRONMENT_KEY" \
  --argjson judges "$JUDGES_JSON" \
  --argjson config "$CONFIG_SUMMARY" \
  --argjson targeting "$TARGET_SUMMARY" \
  --argjson metrics "$METRICS_SUMMARY" \
  --argjson verbose "$VERBOSE" \
  --arg configUrl "$CONFIG_URL" \
  --arg monitoringUrl "$MONITORING_URL" \
  --arg fidelityUrl "$FIDELITY_URL" \
  --arg disciplineUrl "$DISCIPLINE_URL" \
  --arg judgesTabUrl "$JUDGES_TAB_URL" \
  --arg docsJudges "$DOCS_JUDGES" \
  --arg docsOnline "$DOCS_ONLINE" \
  --arg docsMonitor "$DOCS_MONITOR" \
  --arg docsMetricsApi "$DOCS_METRICS_API" \
  --arg fidelityMetric "$LD_JUDGE_FIDELITY_METRIC" \
  --arg disciplineMetric "$LD_JUDGE_DISCIPLINE_METRIC" '
  ($judges | map(.exists) | all) as $judges_exist
  | ($judges | map(select(.exists) | .metricMatches) | all) as $metrics_ok
  | ($config.hasReckless and $config.hasSkeptic) as $vars_ok
  | ($targeting.fallthroughIsSkeptic == true
      and $targeting.charlieToSkeptic == true
      and $targeting.tobyToReckless == true) as $target_ok
  | {
      configKey: $cfg,
      environment: $env,
      healthy: ($judges_exist and $metrics_ok and $vars_ok and $target_ok),
      judges: $judges,
      config: $config,
      targeting: $targeting,
      metrics: $metrics
    }
  | if $verbose == 1 then . + {
      links: {
        agentConfig: $configUrl,
        monitoring: $monitoringUrl,
        sourceFidelityJudge: $fidelityUrl,
        recommendationDisciplineJudge: $disciplineUrl,
        judgesTab: $judgesTabUrl,
        docsJudges: $docsJudges,
        docsOnlineEvaluations: $docsOnline,
        docsMonitor: $docsMonitor,
        docsMetricsApi: $docsMetricsApi
      },
      events: [
        { key: "$ld:ai:generation:success", name: "AI completion success (draft / rewrite)" },
        { key: "$ld:ai:generation:error", name: "AI completion error" },
        { key: $fidelityMetric, name: "Source Fidelity judge score" },
        { key: $disciplineMetric, name: "Recommendation Discipline judge score" }
      ]
    } else . end
')"

if [[ "$JSON" -eq 1 ]]; then
  echo "$STATUS_JSON" | jq .
  exit 0
fi

echo "$STATUS_JSON" | jq -r '
  [
      "Agent Config Key: \(.configKey)",
      "Environment: \(.environment)\(if .metrics != null then "  (last \(.metrics.lookbackHours)h)" else "" end)",
      "Healthy: \(if .healthy then "yes" else "NO — check judges / variations / name targeting" end)",
      "",
      "Judges:",
      (.judges[] |
        "  \(if .exists then "✓" else "✗" end) \(.key)"
        + (if .exists then
            "  mode=\(.mode // "?")  metric=\(.evaluationMetricKey // "n/a")"
            + (if .metricMatches then "" else "  (expected \(.expectedEvaluationMetricKey))" end)
            + (if .modelHint then "  model=\(.modelHint)" else "" end)
          else
            "  (missing — run ./create-judges.sh)"
          end)
      ),
      "",
      "Completion variations:",
      "  \(if .config.hasReckless then "✓" else "✗" end) reckless-hype (Toby)",
      "  \(if .config.hasSkeptic then "✓" else "✗" end) concise-skeptic (Charlie / rewrite)",
      (.config.variations[]? | "    \(.key): model=\(.modelName // .modelConfigKey // "n/a")"),
      "",
      "Targeting:",
      "  on=\(.targeting.on)  fallthrough=\(.targeting.fallthroughVariation // "n/a")\(if .targeting.fallthroughIsSkeptic then " (skeptic ✓)" else " (want concise-skeptic)" end)",
      "  \(if .targeting.charlieToSkeptic then "✓" else "✗" end) Conservative Charlie → concise-skeptic",
      "  \(if .targeting.tobyToReckless then "✓" else "✗" end) Thoughtless Toby → reckless-hype"
    ]
  + (if .metrics != null then [
      "",
      "Metrics (last \(.metrics.lookbackHours)h):",
      "  generationSuccessCount=\(.metrics.generationSuccessCount)  generationErrorCount=\(.metrics.generationErrorCount)",
      (if .metrics.totalTokens != null then
        "  tokens total=\(.metrics.totalTokens)  (in=\(.metrics.inputTokens // "n/a") out=\(.metrics.outputTokens // "n/a"))"
      else empty end)
    ] else [] end)
  | .[]
'

if [[ "$VERBOSE" -eq 1 ]]; then
  cat <<EOF

Links:
  Agent Config:     ${CONFIG_URL}
  Monitoring:       ${MONITORING_URL}
                    (Generations + judge scores — pick env ${LD_ENVIRONMENT_KEY})
  Source Fidelity:  ${FIDELITY_URL}
  Rec. Discipline:  ${DISCIPLINE_URL}
  Judges tab:       ${JUDGES_TAB_URL}
  Docs judges:      ${DOCS_JUDGES}
  Docs online eval: ${DOCS_ONLINE}
  Docs monitor:     ${DOCS_MONITOR}
  Docs metrics:     ${DOCS_METRICS_API}

Event key → Event name
  \$ld:ai:generation:success              →  AI completion success (draft / rewrite)
  \$ld:ai:generation:error                →  AI completion error
  ${LD_JUDGE_FIDELITY_METRIC}      →  Source Fidelity judge score
  ${LD_JUDGE_DISCIPLINE_METRIC} →  Recommendation Discipline judge score

Demo tip: Thoughtless Toby should FAIL both judges and rewrite once as Charlie.
EOF
fi

echo "note: LD Monitoring can lag ~1 min after Generate / judge evaluate; re-run if counts look stale." >&2
echo "note: programmatic create_judge scores may need tracker wiring to show on Monitoring — UI attached judges are optional." >&2
