# 20-multi-arm-bandit

**Status: stub — not implemented yet.**

A **multi-armed bandit** on the grid navigator. Same kind of flag as
[01-abcd-test](../01-abcd-test/): several variations, one username context.
The difference is the split. `01` sets percentages and leaves them. A bandit
watches a metric and shifts traffic toward the variation that is winning,
while still sending some traffic to the others.

[53-mobile-experiment](../../50-mobile/53-mobile-experiment/) stays in
`50-mobile`. That lesson is two phone platforms. This one is the grid.

Keywords: **Experimentation** · **multi-armed bandit** · **Thompson Sampling** ·
**metrics**

Docs: [Multi-armed bandits](https://launchdarkly.com/docs/home/multi-armed-bandits)

## Intended aha

The header label (or another small, visible variation) changes share over the
run. Early on, the arms are close. After the metric reports, one arm gets
more of the usernames. The grid chrome stays the same.

## Do not

- Build this under `50-mobile/` or reuse `acme-mobile-onboarding-v2`
- Treat it as a fixed percentage rollout — that is `01` and
  [16-percentage-rollout](../../10-code-control/16-percentage-rollout/)
- Teach a guarded rollout here — that is [15-guarded-rollout](../15-guarded-rollout/)

## When implementing

1. Write `application.md`: dedicated flag key, metric, randomization unit,
   and how often allocation updates.
2. Grid app plus a small runner that sends exposures and metric events, same
   shape as `01`'s experiment utility.
3. REST to create the flag, the metric, and the bandit (`type: mab`).

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
