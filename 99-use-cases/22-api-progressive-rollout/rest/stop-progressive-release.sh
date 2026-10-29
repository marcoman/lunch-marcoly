#!/usr/bin/env bash
# Stop the active progressive release.
#
# Default resolution rolls every phase back to the original variation
# and removes pending phases. This example has one phase, so roll-back
# serves none again. Pass forward to serve green to the whole phase.
#
# LaunchDarkly: stop an environment release
# https://launchdarkly.com/docs/api/environment-releases-beta/stop-an-environment-release

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

choice="${1:-back}"
case "${choice}" in
  back)
    resolution="roll_back_all_phases_and_remove_pending_phases"
    ;;
  forward)
    resolution="roll_forward_all_phases"
    ;;
  -h|--help)
    echo "usage: $0 [back|forward]"
    exit 0
    ;;
  *)
    echo "error: use back or forward" >&2
    exit 1
    ;;
esac

query="queryfilter=kind%3Aequals%3Aprogressive&limit=5"
listing="$(api_beta GET "$(releases_path)?${query}")"
release_id="$(echo "${listing}" | jq -r '[.items[] | select(.endedAt == null)][0].id // empty')"

if [[ -z "${release_id}" ]]; then
  echo "No active progressive release on ${FLAG_KEY}."
  echo "${listing}" | jq '{totalCount, newest: (.items[0].status // null)}'
  exit 0
fi

echo "Stopping ${release_id} with ${resolution}..."
api_beta PUT "$(releases_path)/${release_id}/stop" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg resolution "${resolution}" '{
    resolution: $resolution,
    comment: "22-api-progressive-rollout: stop progressive release"
  }')" | jq '{id, kind, status, statusReason, endedAt}'
