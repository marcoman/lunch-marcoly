#!/usr/bin/env bash
# Delete the approval lab flag. Pending requests go with it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

echo "Deleting ${FLAG_KEY}..."
api DELETE "/flags/${LD_PROJECT_KEY}/${FLAG_KEY}"
echo "Deleted."
