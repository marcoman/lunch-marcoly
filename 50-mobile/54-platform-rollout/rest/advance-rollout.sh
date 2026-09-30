#!/usr/bin/env bash
# State 2: add ios to the platform clause. Android stays included.
# Semantic patch addValuesToClause:
# https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

FLAG_KEY="enable-mobile-platform-rollout"
project="$(jq -nr --arg v "$LD_PROJECT_KEY" '$v|@uri')"
flag="$(jq -nr --arg v "$FLAG_KEY" '$v|@uri')"
environment="$(jq -nr --arg v "$LD_ENVIRONMENT_KEY" '$v|@uri')"

flag_json="$(api_ok GET "/flags/${project}/${flag}?env=${environment}")"
clause="$(jq -c --arg env "$LD_ENVIRONMENT_KEY" '
  [.environments[$env].rules[]?
    | . as $rule
    | .clauses[]?
    | select(.attribute == "platform" and .op == "in" and (.negate | not))
    | {ruleId: $rule._id, clauseId: ._id, values: .values}]
  | .[0] // empty
' <<<"$flag_json")"

if [[ "$clause" == "null" || -z "$clause" ]]; then
  echo "error: no platform clause on ${FLAG_KEY}. Run ./create-flag.sh first." >&2
  exit 1
fi

if jq -e '(.values // []) | index("ios") != null' >/dev/null <<<"$clause"; then
  echo "Already includes ios. Platform values: $(jq -r '(.values // []) | join(", ")' <<<"$clause")"
  exit 0
fi

patch="$(jq -nc \
  --arg environmentKey "$LD_ENVIRONMENT_KEY" \
  --arg ruleId "$(jq -r '.ruleId' <<<"$clause")" \
  --arg clauseId "$(jq -r '.clauseId' <<<"$clause")" '{
    environmentKey: $environmentKey,
    comment: "54-platform-rollout state 2: add ios",
    instructions: [{
      kind: "addValuesToClause",
      ruleId: $ruleId,
      clauseId: $clauseId,
      values: ["ios"]
    }]
  }')"

api_ok PATCH "/flags/${project}/${flag}" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "$patch" >/dev/null

echo "Added ios. Platform values: android, ios"
