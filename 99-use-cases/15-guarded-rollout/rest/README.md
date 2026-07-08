# REST provisioning — 15-guarded-rollout

Shell scripts to create the highlight flag, guardrail metrics, and inspect guarded-rollout state via the LaunchDarkly REST API.

> In this example, we have a guarded rollout over **12 minutes** in **four equal stages**: **10%**, **20%**, **30%**, and **50%** of users receive the green highlight.

Configure the three guardrail metrics with `./create-metrics.sh`, then run `./configure-guarded-rollout.sh` to prepare targeting JSON and complete the guarded rollout in the LaunchDarkly UI.

## Prerequisites

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
chmod +x *.sh
```

## Scripts

| Script | Purpose |
|--------|---------|
| [create-flag.sh](create-flag.sh) | Create string flag; turn **off** in target environment |
| [create-metrics.sh](create-metrics.sh) | Create the three guardrail metrics (idempotent) |
| [get-metrics.sh](get-metrics.sh) | Show metric keys, event keys, and success criteria |
| [configure-guarded-rollout.sh](configure-guarded-rollout.sh) | Create metrics, prep flag, emit `guarded-rollout-targeting.json` |
| [get-guarded-rollout.sh](get-guarded-rollout.sh) | Show guarded-rollout state (`expand=guardedRollout`) |
| [start-guarded-rollout.sh](start-guarded-rollout.sh) | Simulate stage schedule via manual percentage updates |
| [set-rollout-percent.sh](set-rollout-percent.sh) | Set a single percentage (`0` = off, `100` = all green) |
| [get-flag.sh](get-flag.sh) | Show on/off state and fallthrough rollout |
| [stop-rollout.sh](stop-rollout.sh) | Turn flag off (all users receive `none`) |

## Typical workflow

```bash
./create-flag.sh
./create-metrics.sh
./configure-guarded-rollout.sh
# Complete guarded rollout in LaunchDarkly UI (Default rule → Guarded rollout)
./get-guarded-rollout.sh

# Or simulate percentages without guarded-rollout monitoring:
./start-guarded-rollout.sh          # runs ~12 minutes

# Or set percentages manually:
./set-rollout-percent.sh 10
./set-rollout-percent.sh 30
./get-flag.sh
./stop-rollout.sh
```

Override stage duration (seconds) for testing:

```bash
STAGE_SECONDS=30 ./start-guarded-rollout.sh
```

## Notes

- `./configure-guarded-rollout.sh` does **not** start a guarded rollout via REST. LaunchDarkly ignores `guardedRolloutConfig` on semantic patch. It creates metrics, turns the flag on with off variation `none`, and writes targeting JSON for the UI.
- `./get-guarded-rollout.sh` and the monitor script detect UI guarded rollouts via `fallthrough.rollout.experimentAllocation.type == "measuredRollout"` (the `expand=guardedRollout` field is often null even when active).
- `./start-guarded-rollout.sh` only updates percentage rollouts manually; it does not attach metrics or use LaunchDarkly guarded-rollout monitoring.
- See [../README.md](../README.md) for curl examples and UI walkthrough.
