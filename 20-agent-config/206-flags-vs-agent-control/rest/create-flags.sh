#!/usr/bin/env bash
# LaunchDarkly: feature flags — string, boolean, and JSON variations
# Creates the Separate flags source (four flags) and the JSON flag source (one body).
# Charlie name rule, Toby fallthrough. Judge on for both personas.
# https://launchdarkly.com/docs/api/feature-flags/post-feature-flag
# https://launchdarkly.com/docs/sdk/features/flag-types
# https://launchdarkly.com/docs/home/flags/target

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Flag endpoints use the stable API version. common.sh defaults to beta for AgentControl.
export LD_API_VERSION=20240415
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq
require_environment

MESSAGES_DIR="${SCRIPT_DIR}/messages"
SKEPTIC_SYSTEM="$(cat "${MESSAGES_DIR}/skeptic-system.txt")"
SKEPTIC_USER="$(cat "${MESSAGES_DIR}/skeptic-user.txt")"
RECKLESS_SYSTEM="$(cat "${MESSAGES_DIR}/reckless-system.txt")"
RECKLESS_USER="$(cat "${MESSAGES_DIR}/reckless-user.txt")"

variation_id_by_name() {
  local flag_json="$1"
  local name="$2"
  jq -r --arg name "$name" '.variations[] | select(.name == $name) | ._id' <<<"$flag_json" | head -n1
}

ensure_flag() {
  local key="$1"
  local body="$2"
  local status
  status="$(api_status GET "/flags/${LD_PROJECT_KEY}/${key}")"
  if [[ "$status" == "200" ]]; then
    echo "Flag ${key} already exists — leaving variations in place."
    return 0
  fi
  echo "==> Creating ${key}"
  api_ok POST "/flags/${LD_PROJECT_KEY}" \
    -H "Content-Type: application/json" \
    -d "$body" | jq '{key, name, kind, variations: [.variations[]? | {name}]}'
}

target_charlie() {
  local key="$1"
  local fallthrough_name="$2"
  local charlie_name="$3"
  local off_name="$4"
  local flag_json charlie_id fallthrough_id off_id rule_count patch

  flag_json="$(api_ok GET "/flags/${LD_PROJECT_KEY}/${key}?env=${LD_ENVIRONMENT_KEY}")"
  charlie_id="$(variation_id_by_name "$flag_json" "$charlie_name")"
  fallthrough_id="$(variation_id_by_name "$flag_json" "$fallthrough_name")"
  off_id="$(variation_id_by_name "$flag_json" "$off_name")"
  rule_count="$(jq -r --arg env "$LD_ENVIRONMENT_KEY" '(.environments[$env].rules // []) | length' <<<"$flag_json")"

  if [[ -z "$charlie_id" || "$charlie_id" == "null" || -z "$fallthrough_id" || "$fallthrough_id" == "null" ]]; then
    echo "error: could not resolve variation ids on ${key}" >&2
    exit 1
  fi

  echo "==> Targeting ${key}: Charlie → ${charlie_name}, fallthrough → ${fallthrough_name}"
  patch="$(jq -n \
    --arg env "$LD_ENVIRONMENT_KEY" \
    --arg charlie "$charlie_id" \
    --arg fallthrough "$fallthrough_id" \
    --arg off "$off_id" \
    --argjson has_rules "$rule_count" \
    '{
      environmentKey: $env,
      comment: "26: Charlie name rule, Toby fallthrough",
      instructions: (
        [
          {kind: "turnFlagOn"},
          {kind: "updateFallthroughVariationOrRollout", variationId: $fallthrough},
          (if $off != "" and $off != "null" then {kind: "updateOffVariation", variationId: $off} else empty end)
        ]
        + (if $has_rules == 0 then [
            {
              kind: "addRule",
              description: "Conservative Charlie",
              variationId: $charlie,
              clauses: [{
                contextKind: "user",
                attribute: "name",
                op: "in",
                negate: false,
                values: ["Conservative Charlie"]
              }]
            }
          ] else [] end)
      )
    }')"
  api_ok PATCH "/flags/${LD_PROJECT_KEY}/${key}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "$patch" | jq --arg env "$LD_ENVIRONMENT_KEY" \
      '.environments[$env] | {on, fallthrough, rules: [.rules[]? | {description, clauses: [.clauses[]? | {attribute, values}]}]}'
}

MODEL_BODY="$(jq -n \
  --arg best "$LD_MODEL_BEST_ID" \
  --arg simple "$LD_MODEL_SIMPLE_ID" \
  '{
    key: "configure-briefing-model",
    name: "Configure: briefing model",
    description: "26 separate flags. Model id for the equity briefing.",
    temporary: false,
    tags: ["lunch-marcoly", "26-flags-vs-agent-control", "string"],
    variations: [
      {value: $simple, name: "reckless-hype", description: "Toby fallthrough"},
      {value: $best, name: "concise-skeptic", description: "Charlie"}
    ],
    defaults: {onVariation: 0, offVariation: 0}
  }')"

SYSTEM_BODY="$(jq -n \
  --arg reckless "$RECKLESS_SYSTEM" \
  --arg skeptic "$SKEPTIC_SYSTEM" \
  '{
    key: "configure-briefing-system-prompt",
    name: "Configure: briefing system prompt",
    description: "26 separate flags. System prompt text.",
    temporary: false,
    tags: ["lunch-marcoly", "26-flags-vs-agent-control", "string"],
    variations: [
      {value: $reckless, name: "reckless-hype", description: "Toby fallthrough"},
      {value: $skeptic, name: "concise-skeptic", description: "Charlie"}
    ],
    defaults: {onVariation: 0, offVariation: 0}
  }')"

USER_BODY="$(jq -n \
  --arg reckless "$RECKLESS_USER" \
  --arg skeptic "$SKEPTIC_USER" \
  '{
    key: "configure-briefing-user-prompt",
    name: "Configure: briefing user prompt",
    description: "26 separate flags. User prompt template with {{ stories }}.",
    temporary: false,
    tags: ["lunch-marcoly", "26-flags-vs-agent-control", "string"],
    variations: [
      {value: $reckless, name: "reckless-hype", description: "Toby fallthrough"},
      {value: $skeptic, name: "concise-skeptic", description: "Charlie"}
    ],
    defaults: {onVariation: 0, offVariation: 0}
  }')"

JUDGE_BODY="$(jq -n '{
  key: "enable-briefing-judge",
  name: "Enable: briefing judge",
  description: "26 separate flags. True scores the draft. False leaves the output plain.",
  temporary: false,
  tags: ["lunch-marcoly", "26-flags-vs-agent-control", "boolean"],
  variations: [
    {value: true, name: "On", description: "Score the draft"},
    {value: false, name: "Off", description: "Skip the judge"}
  ],
  defaults: {onVariation: 0, offVariation: 1}
}')"

JSON_CHARLIE="$(jq -n \
  --arg model "$LD_MODEL_BEST_ID" \
  --arg system "$SKEPTIC_SYSTEM" \
  --arg user "$SKEPTIC_USER" \
  '{model: $model, systemPrompt: $system, userPrompt: $user, judge: true}')"
JSON_TOBY="$(jq -n \
  --arg model "$LD_MODEL_SIMPLE_ID" \
  --arg system "$RECKLESS_SYSTEM" \
  --arg user "$RECKLESS_USER" \
  '{model: $model, systemPrompt: $system, userPrompt: $user, judge: true}')"
JSON_BODY="$(jq -n \
  --argjson toby "$JSON_TOBY" \
  --argjson charlie "$JSON_CHARLIE" \
  '{
    key: "configure-briefing-json",
    name: "Configure: briefing JSON",
    description: "26 JSON flag. One body: model, systemPrompt, userPrompt, judge.",
    temporary: false,
    tags: ["lunch-marcoly", "26-flags-vs-agent-control", "json"],
    variations: [
      {value: $toby, name: "reckless-hype", description: "Toby fallthrough"},
      {value: $charlie, name: "concise-skeptic", description: "Charlie"}
    ],
    defaults: {onVariation: 0, offVariation: 0}
  }')"

ensure_flag "configure-briefing-model" "$MODEL_BODY"
ensure_flag "configure-briefing-system-prompt" "$SYSTEM_BODY"
ensure_flag "configure-briefing-user-prompt" "$USER_BODY"
ensure_flag "enable-briefing-judge" "$JUDGE_BODY"
ensure_flag "configure-briefing-json" "$JSON_BODY"

target_charlie "configure-briefing-model" "reckless-hype" "concise-skeptic" "reckless-hype"
target_charlie "configure-briefing-system-prompt" "reckless-hype" "concise-skeptic" "reckless-hype"
target_charlie "configure-briefing-user-prompt" "reckless-hype" "concise-skeptic" "reckless-hype"
target_charlie "enable-briefing-judge" "On" "On" "Off"
target_charlie "configure-briefing-json" "reckless-hype" "concise-skeptic" "reckless-hype"

echo "Done."
echo "  separate flags: configure-briefing-model, configure-briefing-system-prompt, configure-briefing-user-prompt, enable-briefing-judge"
echo "  json flag:      configure-briefing-json"
