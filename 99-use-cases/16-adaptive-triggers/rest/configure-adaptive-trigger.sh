#!/usr/bin/env bash
# Provision resources and print the adaptive-trigger UI configuration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/create-flag.sh"
"${SCRIPT_DIR}/create-metric.sh"

FLAG_URL="${LD_APP_HOST:-${LD_API_HOST}}/projects/${LD_PROJECT_KEY}/flags/${FLAG_KEY}?env=${LD_ENVIRONMENT_KEY}&selected-env=${LD_ENVIRONMENT_KEY}"

cat <<EOF

The adaptive trigger itself is a REQUIRED MANUAL STEP. The REST API creates the
flag and the metric only. Until the trigger exists in the UI, nothing watches
the metric and the variation will never switch.

${FLAG_URL}

Complete the adaptive trigger in the LaunchDarkly UI:

1. Flags → enable-adaptive-grid-highlight → ${LD_ENVIRONMENT_KEY} → Targeting.
2. In Rules, choose Add adaptive trigger.

On that dialog you only need to SET TWO FIELDS:

  a. Source, second menu: Adaptive: grid navigation latency
     (metric key: adaptive-grid-nav-latency-metric).
     The first menu is already LaunchDarkly hosted metrics.
  b. Alert threshold: 200 milliseconds.

Then VERIFY these before pressing Add:

  c. Switch variation to: Safe: no highlight — this is the point of the lab.
  d. Alert window: pick 1 minute if offered. Latency must stay above the
     threshold for this entire window before the trigger fires, so a 30 minute
     window means a 30 minute demo. Enable Auto-report in the app to keep the
     metric fed.

Type (Constant), Condition (Above), Cooldown, and Evaluation delay keep their
defaults. Notifications are optional. Cooldown blocks a second fire until it
elapses, so note whatever value the UI shows.

If Add adaptive trigger does not appear, the feature is not enabled for this
account or plan. Nothing in this lab can substitute for it.

Do not create a webhook-style generic flag trigger: that is a different product.
Do not run an experiment on this flag while using its adaptive trigger.

Then start the Node app and use its Start live button. After the demo, Stop
turns targeting off; remove the adaptive trigger in the UI yourself. Verify the
trigger fired by watching the Default rule card, or by re-running
./get-status.sh: the default rule changes from green to none, and the flag
audit log gains an entry attributed to the trigger.
EOF
