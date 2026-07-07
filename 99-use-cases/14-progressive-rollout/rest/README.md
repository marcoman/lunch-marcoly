# REST provisioning — 14-progressive-rollout

Shell scripts to create the highlight flag and configure **progressive rollout** percentages via the LaunchDarkly REST API.

> In this example, we have a progressive rollout over **15 minutes** in **five equal stages**: **10%**, **20%**, **40%**, **60%**, and **100%** of users receive the green highlight.

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
| [start-progressive-rollout.sh](start-progressive-rollout.sh) | Run full 15-minute schedule (10→20→40→60→100%, 3 min each) |
| [set-rollout-percent.sh](set-rollout-percent.sh) | Set a single percentage (`0` = off, `100` = all green) |
| [get-flag.sh](get-flag.sh) | Show on/off state and fallthrough rollout |
| [stop-rollout.sh](stop-rollout.sh) | Turn flag off (all users receive `none`) |

## Typical workflow

```bash
./create-flag.sh
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

- Weights in curl/API calls are **thousandths of a percent** (10000 = 10%).
- LaunchDarkly UI **Progressive rollout** automates stage timing; these scripts simulate the same percentages via REST for environments where you prefer curl or CI.
- See [../README.md](../README.md) for curl examples and UI walkthrough.
