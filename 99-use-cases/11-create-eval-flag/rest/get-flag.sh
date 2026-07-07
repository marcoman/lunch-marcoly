#!/usr/bin/env bash
# Show highlight flag state in the target environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

fetch_flag | jq \
  --arg env "${LD_ENVIRONMENT_KEY}" \
  '{
    key,
    name,
    variations: [.variations[] | {value, name}],
    environment: {
      key: $env,
      on: .environments[$env].on,
      offVariation: .variations[.environments[$env].offVariation // 0].value,
      fallthroughVariation: .variations[.environments[$env].fallthrough.variation // 0].value
    }
  }'
