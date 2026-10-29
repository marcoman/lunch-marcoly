# 22-api-progressive-rollout

Start a progressive rollout with the environment releases beta API. The grid highlight moves from `none` to `green` in five steps: **10%**, **20%**, **40%**, **60%**, **100%**. Each step lasts **1 minute**.

Example 14 uses the same schedule and finishes the rollout in the UI. This example `POST`s the release. No metrics are included, so the release kind is **progressive**.

The API will not release the default rule. The start call creates one rule whose clause matches every `user` context.

## Prerequisites

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="your-project"
export LD_ENVIRONMENT_KEY="your-environment"
export LD_SDK_KEY="sdk-..."
```

## Run

```bash
cd rest
chmod +x *.sh
./create-flag.sh
```

In another terminal, start the grid and log in once. That gives the flag a recent user evaluation, which the start health check looks for.

```bash
cd python
python 22-api-progressive-rollout.py
```

Open http://127.0.0.1:8780/ and log in. On the Release tab, click **Start progressive release**. **Stop** rolls that release back to `none`. **Reset** turns the flag off. **Try next** samples another username by incrementing a trailing number. The schedule is a percentage of user contexts at each step, held for a fixed time: **10%**, **20%**, **40%**, **60%**, **100%**, one minute each.

`rest/start-progressive-release.sh` sends the same body.

```bash
cd rest
./get-progressive-release.sh
```

Shorter steps for a lab. The button uses the same variable when Python is started with it:

```bash
STAGE_SECONDS=30 python ../python/22-api-progressive-rollout.py
STAGE_SECONDS=30 ./start-progressive-release.sh
```

A flag with no recent evaluations fails `health_checks_failed`. Log in on the grid, or pass `--bypass-health-checks`.

Stop rolls the single phase back to `none` and removes it:

```bash
./stop-progressive-release.sh          # back
./stop-progressive-release.sh forward  # serve green now
```

One evaluation without the browser:

```bash
cd python && python 22-api-progressive-rollout.py --evaluate-once alice
```

## What the call does

`POST /api/v2/projects/{projectKey}/flags/{flagKey}/environments/{environmentKey}/releases`

Header: `LD-API-Version: beta`.

| Field | This example |
|-------|----------------|
| `originalVariationId` | `none` |
| `targetVariationId` | `green` |
| `randomizationUnit` | `user` |
| `metrics` | omitted |
| `phases` | one rule, five steps |
| `cleanupBehavior` | `remove_rules_and_update_default_rule` |

[Environment releases (beta)](https://launchdarkly.com/docs/api/environment-releases)

## Layout

| Piece | Where |
|-------|--------|
| Grid | [python/](python/) on **:8780** |
| Start, read, stop | [rest/](rest/) |
| Flag only, off | [terraform/](terraform/) |
