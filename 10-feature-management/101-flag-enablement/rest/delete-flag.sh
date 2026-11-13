#!/usr/bin/env bash
# LaunchDarkly capability: REST API — delete feature flag
# Permanently deletes a flag. This cannot be undone.
# See: https://launchdarkly.com/docs/api/feature-flags/delete-feature-flag

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

echo "Deleting flag ${FLAG_KEY} from project ${LD_PROJECT_KEY}..."
api DELETE "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" -w "\nHTTP %{http_code}\n"

echo "Done. Verify the flag no longer appears in the LaunchDarkly UI."
