#!/usr/bin/env bash
# Run the full 15-minute guarded rollout schedule via REST percentage updates.
#
# NOTE: This simulates stage percentages only. For a real guarded rollout with
# metric monitoring and auto-rollback, use ./configure-guarded-rollout.sh instead.
#
# In this example, we have a guarded rollout over 12 minutes in four equal
# stages: 10%, 20%, 30%, and 50% of users receive the green highlight.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

STAGE_SECONDS="${STAGE_SECONDS:-180}"
PERCENTAGES=(10 20 30 50)

echo "Guarded rollout schedule for ${FLAG_KEY}:"
echo "  Duration: 12 minutes (${STAGE_SECONDS}s per stage)"
for i in "${!PERCENTAGES[@]}"; do
  start=$((i * STAGE_SECONDS / 60))
  end=$(((i + 1) * STAGE_SECONDS / 60))
  echo "  Stage $((i + 1)) (${start}:00–${end}:00): ${PERCENTAGES[$i]}% green"
done
echo

for i in "${!PERCENTAGES[@]}"; do
  pct="${PERCENTAGES[$i]}"
  echo "=== Stage $((i + 1))/${#PERCENTAGES[@]}: ${pct}% green ==="
  "${SCRIPT_DIR}/set-rollout-percent.sh" "${pct}"
  if (( i + 1 < ${#PERCENTAGES[@]} )); then
    echo "Waiting ${STAGE_SECONDS}s until next stage..."
    sleep "${STAGE_SECONDS}"
  fi
done

last_pct="${PERCENTAGES[${#PERCENTAGES[@]}-1]}"
echo
echo "Simulated percentage schedule complete — ${last_pct}% green."
