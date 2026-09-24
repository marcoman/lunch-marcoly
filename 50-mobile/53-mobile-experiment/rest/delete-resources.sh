#!/usr/bin/env bash
# Permanently delete this lesson's flag and metric. Requires explicit opt-in.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"
require_jq

if [[ "${1:-}" != "--yes" ]]; then
  echo "usage: $0 --yes" >&2
  echo "This permanently deletes the flag and metric from ${LD_PROJECT_KEY}." >&2
  exit 2
fi

project="$(urlencode "$LD_PROJECT_KEY")"
for resource in \
  "/flags/${project}/acme-mobile-onboarding-v2" \
  "/metrics/${project}/mobile_onboarding_completed"; do
  api_request DELETE "$resource"
  case "$API_HTTP_STATUS" in
    200|202|204) echo "Deleted ${resource}." ;;
    404) echo "Already absent: ${resource}." ;;
    *)
      echo "error: DELETE ${resource} returned HTTP ${API_HTTP_STATUS}" >&2
      jq . <<<"$API_RESPONSE" 2>/dev/null || printf '%s\n' "$API_RESPONSE" >&2
      exit 1
      ;;
  esac
done
