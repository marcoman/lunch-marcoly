#!/usr/bin/env bash
# Run the 15-minute progressive rollout schedule via REST percentage updates.
#
# In this example, we have a progressive rollout over 15 minutes in five equal
# stages: 10%, 20%, 40%, 60%, and 100% of users receive the green highlight.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

STAGE_SECONDS="${STAGE_SECONDS:-180}"
PERCENTAGES=(10 20 40 60 100)

echo "Progressive rollout schedule for ${FLAG_KEY}:"
echo "  Duration: 15 minutes (${STAGE_SECONDS}s per stage)"
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

echo
echo "Progressive rollout complete — 100% green."
