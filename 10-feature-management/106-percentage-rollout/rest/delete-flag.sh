#!/usr/bin/env bash
# Permanently delete the dedicated percentage-rollout flag.
# https://launchdarkly.com/docs/api/feature-flags/delete-feature-flag
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

echo "Deleting ${FLAG_KEY} from ${LD_PROJECT_KEY}..."
api DELETE "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" -w "\nHTTP %{http_code}\n"
