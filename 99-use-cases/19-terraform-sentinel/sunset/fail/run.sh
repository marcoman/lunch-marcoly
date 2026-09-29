#!/usr/bin/env bash
# Print this fixture's policy result: pass or fail.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../.." && pwd)"
policy="$(basename "$(dirname "$here")")"
expect="$(basename "$here")"
exec "$root/run-case.sh" "$policy" "$expect" "$here"
