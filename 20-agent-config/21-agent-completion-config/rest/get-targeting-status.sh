#!/usr/bin/env bash
# LaunchDarkly: AgentControl targeting status snapshot (21-agent-completion-config)
# Demo-facing check: variations + models, name rules, fallthrough, config on.
# https://launchdarkly.com/docs/home/agentcontrol/target
# https://launchdarkly.com/docs/api/agent-control/get-ai-config
# https://launchdarkly.com/docs/api/agent-control/get-ai-config-targeting
#
# Usage:
#   ./get-targeting-status.sh
#   ./get-targeting-status.sh equity-briefing-completion
#   ./get-targeting-status.sh --json
#   ./get-targeting-status.sh --verbose
#   ./get-targeting-status.sh --json --verbose
#
# Optional env:
#   LD_METRICS_LOOKBACK_HOURS  include generation metrics (default 24; set 0 to skip)
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
      sed -n '2,20p' "$0" | sed 's/^# \?//'
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
DOCS_TARGET="https://launchdarkly.com/docs/home/agentcontrol/target"
DOCS_QUICK="https://launchdarkly.com/docs/home/agentcontrol/quickstart"
DOCS_OUTSIDE="https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs"

# Expected demo shape (name targeting from update-name-targeting.sh).
EXPECTED_JSON="$(jq -nc \
  --arg baseline_model "$LD_MODEL_DEFAULT_CONFIG_KEY" \
  --arg skeptic_model "$LD_MODEL_BEST_CONFIG_KEY" \
  --arg reckless_model "$LD_MODEL_SIMPLE_CONFIG_KEY" '
  {
    fallthroughVariation: "baseline-analyst",
    variations: [
      { key: "baseline-analyst", expectedModelConfigKey: $baseline_model, persona: "Neutral Nancy / Amelia (fallthrough)" },
      { key: "concise-skeptic", expectedModelConfigKey: $skeptic_model, persona: "Conservative Charlie" },
      { key: "reckless-hype", expectedModelConfigKey: $reckless_model, persona: "Thoughtless Toby" }
    ],
    nameRules: [
      { name: "Conservative Charlie", variationKey: "concise-skeptic" },
      { name: "Neutral Nancy", variationKey: "baseline-analyst" },
      { name: "Thoughtless Toby", variationKey: "reckless-hype" }
    ]
  }
')"

CONFIG_RAW="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}")"
TARGET_RAW="$(api_ok GET "/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/targeting?env=${LD_ENVIRONMENT_KEY}")"

# Optional metrics (generations) — skip when LOOKBACK_HOURS=0
METRICS_SUMMARY='null'
if [[ "$LOOKBACK_HOURS" != "0" ]]; then
  METRICS_PATH="/projects/${LD_PROJECT_KEY}/ai-configs/${CONFIG_KEY}/metrics?env=${LD_ENVIRONMENT_KEY}&from=${FROM_MS}&to=${TO_MS}"
  METRICS_RAW="$(api_ok GET "${METRICS_PATH}")"
  METRICS_SUMMARY="$(echo "$METRICS_RAW" | jq -c \
    --argjson hours "$LOOKBACK_HOURS" '
    {
      lookbackHours: $hours,
      generationSuccessCount: (.generationSuccessCount // 0),
      generationErrorCount: (.generationErrorCount // 0)
    }
  ')"
fi

STATUS_JSON="$(jq -nc \
  --arg cfg "$CONFIG_KEY" \
  --arg env "$LD_ENVIRONMENT_KEY" \
  --argjson expected "$EXPECTED_JSON" \
  --argjson config "$CONFIG_RAW" \
  --argjson targeting "$TARGET_RAW" \
  --argjson metrics "$METRICS_SUMMARY" \
  --argjson verbose "$VERBOSE" \
  --arg configUrl "$CONFIG_URL" \
  --arg monitoringUrl "$MONITORING_URL" \
  --arg docsTarget "$DOCS_TARGET" \
  --arg docsQuick "$DOCS_QUICK" \
  --arg docsOutside "$DOCS_OUTSIDE" '
  ($config.variations // []) as $cvars
  | ($targeting.variations // []) as $tvars
  | ($targeting.environments[$env] // null) as $e
  | ($e.fallthrough.variation // $e.fallthrough // null) as $ft_raw
  | (
      if ($ft_raw | type) == "number" then ($tvars[$ft_raw].key // $cvars[$ft_raw].key // null)
      elif ($ft_raw | type) == "string" then
        ( ($tvars | map(select(._id == $ft_raw or .key == $ft_raw)) | .[0].key)
          // ($cvars | map(select(.id == $ft_raw or .key == $ft_raw)) | .[0].key)
          // $ft_raw )
      elif ($ft_raw | type) == "object" then
        ( $ft_raw.variation
          | if type == "number" then ($tvars[.].key // $cvars[.].key // null)
            elif type == "string" then
              ( ($tvars | map(select(._id == . or .key == .)) | .[0].key) // . )
            else null end )
      else null end
    ) as $ft_key
  | (
      ($e.rules // [])
      | map(
          . as $rule
          | (
              if ($rule.variation | type) == "number" then ($tvars[$rule.variation].key // null)
              elif ($rule.variationId | type) == "string" then
                ($tvars | map(select(._id == $rule.variationId)) | .[0].key // null)
              else ($rule.variation // null | tostring)
              end
            ) as $vkey
          | ($rule.clauses // []) as $clauses
          | ($clauses | map(select((.attribute // "") == "name")) | .[0]) as $name_clause
          | {
              description: ($rule.description // null),
              variationKey: $vkey,
              names: ($name_clause.values // []),
              attribute: ($name_clause.attribute // null),
              op: ($name_clause.op // null)
            }
        )
    ) as $rules
  | (
      $expected.variations
      | map(
          . as $exp
          | ($cvars | map(select(.key == $exp.key)) | .[0]) as $var
          | {
              key: $exp.key,
              found: ($var != null),
              persona: $exp.persona,
              modelConfigKey: ($var.modelConfigKey // null),
              modelName: ($var.model.modelName // null),
              expectedModelConfigKey: $exp.expectedModelConfigKey,
              modelMatches: (
                ($var.modelConfigKey // "") == $exp.expectedModelConfigKey
                or ($var.model.modelName // "") == ($exp.expectedModelConfigKey | split(".") | .[-1] | gsub("-"; ":"))
                or false
              ),
              messageRoles: ([($var.messages // [])[]?.role] | unique),
              state: ($var.state // null)
            }
        )
    ) as $variation_status
  | (
      $expected.nameRules
      | map(
          . as $exp
          | ($rules | map(select(.names | index($exp.name))) | .[0]) as $hit
          | {
              name: $exp.name,
              expectedVariation: $exp.variationKey,
              matched: ($hit != null and $hit.variationKey == $exp.variationKey),
              actualVariation: ($hit.variationKey // null),
              ruleDescription: ($hit.description // null)
            }
        )
    ) as $name_status
  | (
      ([$variation_status[].found] | all)
      and ([$name_status[].matched] | all)
      and ($ft_key == $expected.fallthroughVariation)
      and (($e.on // false) == true)
    ) as $healthy
  | {
      configKey: $cfg,
      environment: $env,
      healthy: $healthy,
      config: {
        name: $config.name,
        mode: $config.mode,
        variationCount: ($cvars | length)
      },
      targeting: {
        on: ($e.on // null),
        fallthroughVariation: $ft_key,
        expectedFallthrough: $expected.fallthroughVariation,
        fallthroughMatches: ($ft_key == $expected.fallthroughVariation),
        ruleCount: ($rules | length),
        rules: $rules
      },
      variations: $variation_status,
      nameTargeting: $name_status,
      metrics: $metrics
    }
  | if $verbose == 1 then . + {
      links: {
        agentConfig: $configUrl,
        monitoring: $monitoringUrl,
        docsTarget: $docsTarget,
        docsQuickstart: $docsQuick,
        docsConfigOutsideCode: $docsOutside
      },
      personas: [
        { name: "Conservative Charlie", variation: "concise-skeptic" },
        { name: "Neutral Nancy", variation: "baseline-analyst" },
        { name: "Thoughtless Toby", variation: "reckless-hype" },
        { name: "Anonymous Amelia", variation: "baseline-analyst (fallthrough)" }
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
      "Environment: \(.environment)",
      "Healthy: \(if .healthy then "yes" else "NO — check variations / name rules / fallthrough / on" end)",
      "",
      "Targeting:",
      "  on=\(.targeting.on)  fallthrough=\(.targeting.fallthroughVariation // "n/a")\(if .targeting.fallthroughMatches then " (matches)" else " (expected \(.targeting.expectedFallthrough))" end)",
      "  name rules: \(.targeting.ruleCount)",
      "",
      "Variations:",
      (.variations[] |
        "  \(if .found then "✓" else "✗" end) \(.key)  model=\(.modelConfigKey // .modelName // "n/a")\(if .found and (.modelMatches|not) then "  (expected \(.expectedModelConfigKey))" else "" end)  — \(.persona)"
      ),
      "",
      "Name targeting:",
      (.nameTargeting[] |
        "  \(if .matched then "✓" else "✗" end) \(.name) → \(.expectedVariation)\(if .matched then "" else "  (actual=\(.actualVariation // "missing"))" end)"
      )
    ]
  + (if .metrics != null then [
      "",
      "Metrics (last \(.metrics.lookbackHours)h):",
      "  generationSuccessCount=\(.metrics.generationSuccessCount)  generationErrorCount=\(.metrics.generationErrorCount)"
    ] else [] end)
  | .[]
'

if [[ "$VERBOSE" -eq 1 ]]; then
  cat <<EOF

Links:
  Agent Config:  ${CONFIG_URL}
  Monitoring:    ${MONITORING_URL}
  Docs target:   ${DOCS_TARGET}
  Docs quickstart: ${DOCS_QUICK}
  Docs outside code: ${DOCS_OUTSIDE}

Expected personas (context name → variation):
  Conservative Charlie → concise-skeptic
  Neutral Nancy        → baseline-analyst
  Thoughtless Toby     → reckless-hype
  Anonymous Amelia     → baseline-analyst (fallthrough)

If Healthy=NO and fallthrough is wrong: ./update-targeting.sh baseline-analyst
If name rules missing: ./update-name-targeting.sh
EOF
fi

if [[ "$LOOKBACK_HOURS" != "0" ]]; then
  echo "note: LD Monitoring can lag ~1 min after Generate; re-run if counts look stale." >&2
fi
