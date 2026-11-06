# 23-api-guarded-rollout

Start a guarded rollout with the environment releases beta API. The grid highlight moves from `none` to `green` in four steps: **10%** and **20%** for **2 minutes** each, then **30%** and **50%** for **1 minute** each.

Example 15 uses the same percentages and the same three guardrails, and finishes the rollout in the UI. This example `POST`s the release. The metrics make the release kind **guarded**. Example 22 uses the same endpoint and omits metrics, so that release stays progressive.

The latency slider is the violation. Above **200 ms** is the guardrail. Error rate and movement stay in the normal range.

## Prerequisites

```bash
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="your-project"
export LD_ENVIRONMENT_KEY="your-environment"
export LD_SDK_KEY="sdk-..."
```

## Run

```bash
cd python && python 23-api-guarded-rollout.py    # :8784
cd node && npm install && npm start              # :8785
cd java && ./mvnw -q -DskipTests package && java -jar target/23-api-guarded-rollout.jar  # :8786
cd dotnet && dotnet run                          # :8787
```

Open one of those and log in once. Python is **:8784**, Node **:8785**, Java **:8786**, .NET **:8787**. That login gives the flag a recent user evaluation, which the start health check looks for. **Start guarded release** creates `api-guarded-grid-highlight` and the three metrics if they are missing, then POSTs the release. **Try next** increments a trailing number (`marco`, then `marco1`) and the list keeps the latest keys with the variation and the reason. The tally under that list is how many of those keys received green. The Trace section records flag on and off, each new evaluation, percent changes, and rollbacks. The Guardrails tab holds the description of the three metrics.

The consoles only read the flag. Start the release from a web grid, then watch it in a console. Each one re-evaluates every 500 ms and accepts `--evaluate-once alice`.

```bash
cd python-console && python 23-api-guarded-rollout.py
cd node-console && npm install && npm start
cd java-console && ./mvnw -q -DskipTests package && java -jar target/23-api-guarded-rollout.jar
cd go && go run .
cd rust && cargo run
cd cpp && make && ./23-api-guarded-rollout
```

Leave the slider at 50 ms, or raise it above 200 ms and turn on **Report once per second** during the first two stages. Each report samples the logged-in user and `username-1` through `username-23`. Contexts on green send the slider. Contexts on none send 50 ms. The status line says **Monitoring**, then **Rolled back to none** if a guardrail regresses, or **Completed** when the release finishes. Either finish shows the flag targeting URL built from `LD_API_HOST`, `LD_PROJECT_KEY`, `LD_ENVIRONMENT_KEY`, and the flag key. **Stop** rolls the release back. **Reset** stays available, turns the flag off, and removes the phase rule.

## Guardrails

| Metric | What this page sends | What the reader should expect |
|--------|----------------------|-------------------------------|
| `grid-nav-latency` | The slider, in milliseconds, for contexts receiving green. Contexts on none send 50 ms | Lower is better. Above 200 ms on green is the violation. |
| `grid-highlight-error-rate` | Nothing | One event would be a wrong color. Quiet means the rate stays at 0%. |
| `grid-nav-movement` | `1` on each move and each automatic report | Higher is better. One navigation stays at or above the guardrail. |

Start writes those sentences onto the metric descriptions when it creates a metric, and replaces a description that does not already match. The keys are the ones example 15 tested. The flag is dedicated, so `enable-grid-selection-highlight` stays independent.

Variation descriptions name the color. They do not cite a repository URL. This README is the place for the source.

## What the call does

`POST /api/v2/projects/{projectKey}/flags/{flagKey}/environments/{environmentKey}/releases`

Header: `LD-API-Version: beta`.

| Field | This example |
|-------|----------------|
| `originalVariationId` | `none` |
| `targetVariationId` | `green` |
| `randomizationUnit` | `user` |
| `metrics` | the three guardrails, each with `autoRollback: true` |
| `phases` | one rule, four steps |
| `cleanupBehavior` | `remove_rules_and_update_default_rule` |
| `bypassHealthChecks` | `metric_events_any`, `metric_events_with_context` |

The error-rate metric is supposed to have no events, so those two checks are bypassed. The flag still has to have been evaluated. Log in before Start.

A guarded release cannot allocate more than 50%. At 10%, LaunchDarkly serves green to 10%, measures `none` as the control for another 10%, and leaves the rest on `none`.

[Environment releases (beta)](https://launchdarkly.com/docs/api/environment-releases)

## Layout

| Piece | Where |
|-------|--------|
| Web grid | [python/](python/) **:8784**, [node/](node/) **:8785**, [java/](java/) **:8786**, [dotnet/](dotnet/) **:8787** |
| Console | [python-console/](python-console/), [node-console/](node-console/), [java-console/](java-console/), [go/](go/), [rust/](rust/), [cpp/](cpp/) |
