#!/usr/bin/env bash
# Retrieve show-partner-org-badge, including environment targeting.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

FLAG_KEY="${1:-show-partner-org-badge}"
query=""
[[ -n "${LD_ENVIRONMENT_KEY:-}" ]] && query="?env=${LD_ENVIRONMENT_KEY}"
api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}${query}" | jq '{
  key,name,description,tags,
  variations:[.variations[]|{id:._id,value,name}],
  defaults,environments
}'
