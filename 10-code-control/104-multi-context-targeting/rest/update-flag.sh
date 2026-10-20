#!/usr/bin/env bash
# Toggle the flag without editing its provisioned targeting rules.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

if [[ -z "${LD_ENVIRONMENT_KEY:-}" ]]; then
  echo "error: LD_ENVIRONMENT_KEY is required" >&2
  exit 1
fi

ACTION="${1:-on}"
case "$ACTION" in
  on) kind="turnFlagOn" ;;
  off) kind="turnFlagOff" ;;
  *) echo "usage: $0 [on|off]" >&2; exit 1 ;;
esac

api PATCH "/flags/${LD_PROJECT_KEY}/show-partner-org-badge" \
  -H "Content-Type: application/json; domain-model=launchdarkly.semanticpatch" \
  -d "{
    \"environmentKey\":\"${LD_ENVIRONMENT_KEY}\",
    \"comment\":\"14-multi-context-targeting REST example: ${ACTION}\",
    \"instructions\":[{\"kind\":\"${kind}\"}]
  }" | jq ".environments.\"${LD_ENVIRONMENT_KEY}\" | {on,offVariation,fallthrough,rules:[.rules[]?|{description}]}"
