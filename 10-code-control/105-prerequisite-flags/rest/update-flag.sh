#!/usr/bin/env bash
# Toggle parent and/or child on/off. Does not edit the prerequisite.
# https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "error: LD_ENVIRONMENT_KEY is required" >&2
  exit 1
fi

ACTION="${1:-on}"
TARGET="${2:-all}"
case "$ACTION" in
  on) kind="turnFlagOn" ;;
  off) kind="turnFlagOff" ;;
  *) echo "usage: $0 [on|off] [parent|child|all]" >&2; exit 1 ;;
esac

keys=()
case "$TARGET" in
  parent) keys=("$PARENT_KEY") ;;
  child) keys=("$CHILD_KEY") ;;
  all) keys=("$PARENT_KEY" "$CHILD_KEY") ;;
  *) echo "usage: $0 [on|off] [parent|child|all]" >&2; exit 1 ;;
esac

for key in "${keys[@]}"; do
  echo "${ACTION} ${key}..."
  api PATCH "/flags/${LD_PROJECT_KEY}/${key}" \
    -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
    -d "{
      \"environmentKey\":\"${LD_ENVIRONMENT_KEY}\",
      \"comment\":\"15-prerequisite-flags REST: ${ACTION} ${key}\",
      \"instructions\":[{\"kind\":\"${kind}\"}]
    }" | jq --arg key "$key" --arg env "$LD_ENVIRONMENT_KEY" \
      '{key:$key} + (.environments[$env] | {on,offVariation,fallthrough,prerequisites})'
done
