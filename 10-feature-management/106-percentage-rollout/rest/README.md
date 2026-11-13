# REST provisioning — 106-percentage-rollout

Create `enable-grid-selection-highlight-pct` and configure its default rule as
a **static 30% green / 70% none** rollout, bucketed by the `user` context key.

This is a [percentage rollout](https://launchdarkly.com/docs/home/flags/rollouts),
not a time-based progressive rollout.

## Prerequisites

- `curl` and `jq`
- LaunchDarkly API token with flag write access

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `LD_API_ACCESS_TOKEN` | Yes | REST authorization |
| `LD_PROJECT_KEY` | Yes | Project containing the flag |
| `LD_ENVIRONMENT_KEY` | Yes for targeting | Environment receiving the rollout |
| `LD_API_HOST` | No | Defaults to `https://app.launchdarkly.com` |

## Run

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"

chmod +x *.sh
./create-flag.sh
./get-rollout.sh
```

Change the static share for a demo:

```bash
./set-rollout-percent.sh 0
./set-rollout-percent.sh 30
./set-rollout-percent.sh 100
```

`set-rollout-percent.sh <green-percent>` turns the flag on and replaces the
default-rule weights immediately. The argument is the `green` share, from 0
to 100. The remainder is `none`. Bucketing uses the `user` context key.
LaunchDarkly stores each share in thousandths, so 30% is weight `30000`. The
script does not create a schedule and does not move the weights later.

`get-rollout.sh` is read-only. It prints whether the flag is on in
`LD_ENVIRONMENT_KEY`, which context kind the default rule buckets by, and each
variation's percent. Run it before and after `set-rollout-percent.sh` to
confirm the saved weights.

Cleanup:

```bash
./delete-flag.sh
```
