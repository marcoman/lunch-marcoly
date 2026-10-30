# API Guarded Rollout

This document defines **23-api-guarded-rollout** under [99-use-cases](../README.md).

## Goal

Start a **guarded rollout** of the grid highlight with the **environment releases** beta API. The percentages match [15-guarded-rollout](../15-guarded-rollout/): 10%, 20%, 30%, then 50%. The first two stages hold for **2 minutes**. The last two hold for **1 minute**.

[15-guarded-rollout](../15-guarded-rollout/) prepares the same three guardrails and finishes in the UI. [22-api-progressive-rollout](../22-api-progressive-rollout/) uses this endpoint without metrics. This example includes the metrics, so the release kind is guarded.

## Flag

| Key | `api-guarded-grid-highlight` |
|-----|--------------------------------|
| Type | **String** |
| Original variation | `none` |
| Target variation | `green` |

Dedicated key, so `enable-grid-selection-highlight` in example 15 stays independent.

Variation descriptions name what the cell does. They do not include a repository URL.

### Release

One phase. The phase is a new targeting rule, not the default rule. Its clause is:

```json
{"contextKind": "user", "attribute": "kind", "op": "in", "values": ["user"]}
```

| Step | Green traffic | Duration |
|------|---------------|----------|
| 1 | 10% | 2 minutes |
| 2 | 20% | 2 minutes |
| 3 | 30% | 1 minute |
| 4 | 50% | 1 minute |

Allocations in the API are thousandths of a percent: 10% is `10000`. A guarded release cannot exceed `50000` (50%).

The default rule serves `none` while the release runs. `cleanupBehavior` is `remove_rules_and_update_default_rule`.

Every release call sends `LD-API-Version: beta`.

### Guardrails

The metric keys are the ones tested in example 15. Start creates a missing metric and writes a description that says what this page does with it.

| Metric key | Event key | This page |
|------------|-----------|-----------|
| `grid-nav-latency` | `grid-navigation-latency` | Slider value for contexts receiving green. Contexts on none send 50 ms. Above 200 ms on green is the violation. Lower is better. |
| `grid-highlight-error-rate` | `grid-highlight-color-error` | No events. The rate stays at the normal 0%. Lower is better. |
| `grid-nav-movement` | `grid-navigation-count` | `1` per move. Stays at or above one navigation. Higher is better. |

Each metric is attached with `autoRollback: true`. The slider is the control that can cross the latency guardrail. The other two are on the release so the reader can see a normal guardrail beside the one that moves.

Start bypasses `metric_events_any` and `metric_events_with_context` because the error-rate metric is quiet on purpose. It does not bypass the flag-evaluation checks.

## Application behavior

1. Log in with a username. That username is the `user` context key.
2. The page evaluates `api-guarded-grid-highlight`.
3. The selected cell turns green when the variation is `green`.
4. **Start guarded release** POSTs the environment release.
5. A move, or **Report once per second**, samples the logged-in user and `username-1` through `username-23`. Green contexts send the slider. None contexts send 50 ms. Each sends one navigation. None of them send a color error.
6. **Try next** increments a trailing number and evaluates that user. The list shows the variation and the reason. A tally counts green against none for the keys sampled in this session.
7. The Trace section records flag on and off, evaluations, percent changes, and rollbacks as the page receives them.
8. The Guardrails tab describes the three metrics. Latency is the lever.
9. The Release tab shows one status line: **Monitoring**, or **Rolled back to none**. A completed release or a rollback shows the flag targeting URL for this project and environment.

## Acceptance criteria

- [ ] Start creates `api-guarded-grid-highlight` when it is missing, and leaves variation text free of a repository URL
- [ ] Start creates the three metrics when they are missing, with descriptions that say what latency, error rate, and movement do here
- [ ] The release `kind` is `guarded` and the four steps are 10% / 2 min, 20% / 2 min, 30% / 1 min, 50% / 1 min
- [ ] The latency slider reports a number from 0 to 500 ms, and a value above 200 ms is marked as the guardrail
- [ ] Error rate sends no events, and movement sends 1
- [ ] The status line says Monitoring while the release is in progress, and Rolled back to none after a regression or a stop
- [ ] A completed release or a rollback shows the flag targeting URL built from the configured project and environment
- [ ] Reset turns the flag off and removes the phase rule

## Further reading

- [README.md](README.md)
- [Environment releases (beta)](https://launchdarkly.com/docs/api/environment-releases)
- [Guarded rollouts](https://launchdarkly.com/docs/home/releases/guarded-rollouts)
- [15-guarded-rollout](../15-guarded-rollout/) — same guardrails, finished in the UI
- [22-api-progressive-rollout](../22-api-progressive-rollout/) — same endpoint, no metrics
