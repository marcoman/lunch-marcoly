#!/usr/bin/env bash
# Show current flag state and fallthrough rollout.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

fetch_flag | jq --arg env "${LD_ENVIRONMENT_KEY}" '{
  key: .key,
  on: .environments[$env].on,
  offVariation: .variations[.environments[$env].offVariation].value,
  fallthrough: .environments[$env].fallthrough
}'
