#!/usr/bin/env bash
# Permanently delete a 15-prerequisite-flags flag.
# Default: child first, then parent (parent cannot be deleted while it is a prerequisite).
# https://launchdarkly.com/docs/api/feature-flags/delete-feature-flag
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

delete_one() {
  local key="$1"
  echo "Deleting ${key} from ${LD_PROJECT_KEY}..."
  api DELETE "/flags/${LD_PROJECT_KEY}/${key}" -w "\nHTTP %{http_code}\n"
}

if [[ $# -gt 0 ]]; then
  delete_one "$1"
  exit 0
fi

delete_one "$CHILD_KEY"
delete_one "$PARENT_KEY"
echo "Done."
