# REST provisioning — 14-progressive-rollout

Shell scripts to create the highlight flag and inspect or **simulate** progressive rollout percentages via the LaunchDarkly REST API.

> In this example, we have a progressive rollout over **15 minutes** in **five equal stages**: **10%**, **20%**, **40%**, **60%**, and **100%** of users receive the green highlight.

Run `./configure-progressive-rollout.sh` to prepare targeting JSON and complete the progressive rollout in the LaunchDarkly UI.

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
| [configure-progressive-rollout.sh](configure-progressive-rollout.sh) | Prep flag, emit `progressive-rollout-targeting.json` for UI |
| [get-progressive-rollout.sh](get-progressive-rollout.sh) | Show progressive-rollout state (`progressiveRollout` / config) |
| [start-progressive-rollout.sh](start-progressive-rollout.sh) | Simulate stage schedule via manual percentage updates |
| [set-rollout-percent.sh](set-rollout-percent.sh) | Set a single percentage (`0` = off, `100` = all green) |
| [get-flag.sh](get-flag.sh) | Show on/off state, allocation type, and fallthrough |
| [stop-rollout.sh](stop-rollout.sh) | Turn flag off (all users receive `none`) |

## Typical workflow

```bash
./create-flag.sh
./configure-progressive-rollout.sh
# Complete progressive rollout in LaunchDarkly UI (Default rule → Progressive rollout)
./get-progressive-rollout.sh

# Or simulate percentages without UI progressive rollout:
./start-progressive-rollout.sh          # runs ~15 minutes

# Or set percentages manually:
./set-rollout-percent.sh 10
./set-rollout-percent.sh 40
./get-flag.sh
./stop-rollout.sh
```

Override stage duration (seconds) for testing:

```bash
STAGE_SECONDS=30 ./start-progressive-rollout.sh
```

## Notes

- `./configure-progressive-rollout.sh` does **not** start a progressive rollout via REST. LaunchDarkly ignores `progressiveRolloutConfig` on semantic patch. It turns the flag on with off variation `none` and writes targeting JSON for the UI.
- `./get-progressive-rollout.sh` and the monitor script detect UI progressive rollouts via `fallthrough.rollout.experimentAllocation.type == "progressiveRollout"` or `fallthrough.progressiveRolloutConfig`. They warn if `measuredRollout` (guarded rollout) is detected instead.
- `./start-progressive-rollout.sh` only updates percentage rollouts manually; LaunchDarkly does not auto-advance those stages.
- See [../README.md](../README.md) for curl examples and UI walkthrough.
