#!/usr/bin/env bash
# Get highlight flag for segments-by-name.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

api GET "/flags/${LD_PROJECT_KEY}/configure-grid-selection-green-highlight" | jq '{
  key,
  name,
  variations: [.variations[] | {value, name}],
  defaults
}'
