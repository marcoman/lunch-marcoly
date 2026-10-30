# API Progressive Rollout

This document defines **22-api-progressive-rollout** under [99-use-cases](../README.md).

## Goal

Start a **progressive rollout** of the grid highlight with the **environment releases** beta API. The same schedule as [14-progressive-rollout](../14-progressive-rollout/) — 10%, 20%, 40%, 60%, then 100% — is one `POST`. No metrics are sent, so the release kind is progressive.

[14-progressive-rollout](../14-progressive-rollout/) still prepares the flag and finishes the rollout in the UI. This example does not.

## Flag

| Key | `api-progressive-grid-highlight` |
|-----|----------------------------------|
| Type | **String** |
| Original variation | `none` |
| Target variation | `green` |

Dedicated key, so `enable-grid-selection-highlight` in example 14 stays independent.

### Release

One phase. The phase is a new targeting rule, not the default rule. Its clause is:

```json
{"contextKind": "user", "attribute": "kind", "op": "in", "values": ["user"]}
```

| Step | Green traffic | Duration |
|------|---------------|----------|
| 1 | 10% | 1 minute |
| 2 | 20% | 1 minute |
| 3 | 40% | 1 minute |
| 4 | 60% | 1 minute |
| 5 | 100% | 1 minute |

`STAGE_SECONDS` overrides the duration. Allocations in the API are thousandths of a percent: 10% is `10000`.

The default rule serves `none` while the release runs. `cleanupBehavior` is `remove_rules_and_update_default_rule`, so a completed release removes the phase rule and serves `green` from the default rule.

Every call sends `LD-API-Version: beta`.

## Application behavior

1. Log in with a username. That username is the `user` context key.
2. The page evaluates `api-progressive-grid-highlight`.
3. The selected cell turns green when the variation is `green`.
4. **Start progressive release** on the Release tab POSTs the environment release.
5. The Release tab shows the context, the variation, the reason, and the release step read from the API. Elapsed time counts from the moment this page notices the step, and resets on the next step.

The [README](README.md) shows two running examples: step 1 at 10% with `marco` still on `none`, then a nine-key sample at 20% where two keys are `green`.

## Acceptance criteria

- [ ] `rest/create-flag.sh` creates the string flag and leaves it **off**
- [ ] `rest/start-progressive-release.sh` turns the flag on, keeps the default rule at `none`, and `POST`s a progressive release
- [ ] The release `kind` is `progressive` and `metrics` is empty
- [ ] `rest/get-progressive-release.sh` prints the current step
- [ ] `rest/stop-progressive-release.sh` rolls the phase back to `none`
- [ ] The grid shows green for usernames in the current step's bucket

## Further reading

- [README.md](README.md)
- [Environment releases (beta)](https://launchdarkly.com/docs/api/environment-releases)
- [Progressive rollouts](https://launchdarkly.com/docs/home/releases/progressive-rollouts)
- [14-progressive-rollout](../14-progressive-rollout/) — same schedule, finished in the UI
