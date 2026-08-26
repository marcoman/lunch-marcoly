#!/usr/bin/env bash
# Provision resources and print the adaptive-trigger UI configuration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/create-flag.sh"
"${SCRIPT_DIR}/create-metric.sh"

cat <<EOF

Complete the adaptive trigger in the LaunchDarkly UI:

1. Flags → enable-adaptive-grid-highlight → ${LD_ENVIRONMENT_KEY} → Targeting.
2. In Rules, choose Add adaptive trigger.
3. Source: LaunchDarkly hosted metric → Adaptive: grid navigation latency
   (metric key: adaptive-grid-nav-latency-metric).
4. Type: Constant; Condition: Above; Alert threshold: 200 milliseconds.
5. Alert window: 1 minute, or the shortest available.
6. Switch variation to: Safe: no highlight (none).
7. Add an optional notification, then save.

Do not create a webhook-style generic flag trigger: that is a different product.
Do not run an experiment on this flag while using its adaptive trigger.

Then start the Node app and use its Start live button.
EOF
