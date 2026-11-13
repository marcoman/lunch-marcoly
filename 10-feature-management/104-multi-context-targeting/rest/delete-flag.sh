#!/usr/bin/env bash
# Permanently delete the partner-badge flag.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

FLAG_KEY="${1:-show-partner-org-badge}"
echo "Deleting ${FLAG_KEY} from ${LD_PROJECT_KEY}..."
api DELETE "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}" -w "\nHTTP %{http_code}\n"
