#!/usr/bin/env bash
# LaunchDarkly capability: REST API — get feature flag
# Retrieves a single flag by key.
# See: https://launchdarkly.com/docs/api/feature-flags/get-feature-flag

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

FLAG_KEY="${1:-}"
if [[ -z "$FLAG_KEY" ]]; then
  echo "usage: $0 <flag-key>" >&2
  echo "example: $0 show-navigation-move-count" >&2
  exit 1
fi

api GET "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" | jq '{
  key,
  name,
  description,
  temporary,
  tags,
  variations: [.variations[] | {value, name, description}],
  defaults
}'
