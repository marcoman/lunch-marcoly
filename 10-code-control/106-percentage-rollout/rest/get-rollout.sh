#!/usr/bin/env bash
# Print the percentage rollout on the default rule for this environment.
# Read-only. It does not change targeting.
# https://launchdarkly.com/docs/home/flags/rollouts
# https://launchdarkly.com/docs/api/feature-flags/get-feature-flag
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_environment

fetch_flag | jq --arg env "$LD_ENVIRONMENT_KEY" '
  . as $flag
  | ($flag.environments[$env] // {}) as $env_state
  | ($env_state.fallthrough.rollout) as $rollout
  | {
      key: $flag.key,
      environment: $env,
      on: $env_state.on,
      bucketBy: ($rollout.contextKind // null),
      weights: (
        if $rollout then
          [
            $rollout.variations[]
            | {
                value: $flag.variations[.variation].value,
                percent: (.weight / 1000)
              }
          ]
        elif $env_state.fallthrough.variation != null then
          [{
            value: $flag.variations[$env_state.fallthrough.variation].value,
            percent: 100
          }]
        else
          []
        end
      )
    }
'
