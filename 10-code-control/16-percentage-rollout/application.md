# 16-percentage-rollout application specification

This document defines **16-percentage-rollout**.

Baseline login, grid, header positions, session controls, and `X`-only
selection come from
[00-reference-code/application.md](../../00-reference-code/application.md).

## Overview

Teach a **static percentage rollout**. The default rule serves `green` to a
fixed share of users and `none` to the rest. LaunchDarkly assigns each
**username context key** to a bucket; the same key always gets the same
variation until weights change.

This is **not**:

| Example | Difference |
|---------|------------|
| [14-progressive-rollout](../../99-use-cases/14-progressive-rollout/) | Time-staged 10→100% |
| [01-abcd-test](../../99-use-cases/01-abcd-test/) | Four experiment labels |
| [11-flag-enablement](../11-flag-enablement/) | Independent on/off, no rollout |

Keywords: **percentage rollout** · **context key** · **sticky bucketing** ·
**feature flags**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts) ·
[Evaluating flags](https://launchdarkly.com/docs/sdk/features/evaluating)

## The aha

Log in as `alice`, then log out and as `bob`. One session shows a green
highlight; the other stays `X` only. Reload the same username — assignment
does not flip. The dashboard still says **30% / 70%**; the app never randomizes.

## Flag

Do **not** reuse 11's key. Suffix **`pct`**.

| Attribute | Value |
|-----------|-------|
| **Kind** | Enable (operational) |
| **Name** | `Enable: grid selection highlight (pct)` |
| **Key** | `enable-grid-selection-highlight-pct` |
| **Variation type** | string |
| **Variations** | `none`, `green` |
| **Off variation** | `none` |
| **Fallthrough** | Percentage rollout: **30%** `green`, **70%** `none` |
| **Environment default** | **On** (so the rollout is live after provision) |
| **SDK default when offline** | `none` |
| **Tags** | `grid-navigator`, `enable`, `ui`, `string`, `percentage-rollout` |
| **Description** | `16-percentage-rollout. Static 30/70 green/none rollout on username context key. Dedicated key so 11 stays independent. Not a progressive rollout.` |

When the served variation is `green`, the selected cell and username use green.
When `none`, match 00 (`X` only).

## Context

| Kind | Key |
|------|-----|
| `user` | Trimmed login username |

No extra attributes required for the lesson. Do not hash or salt the key in
application code.

## Application generate path

1. Login with a non-empty username.
2. Evaluate `enable-grid-selection-highlight-pct` for that user context.
3. Apply highlight from the variation. Show **Flag value** in the header (or
   lab drawer) so the bucket is visible without opening the dashboard.
4. Keep the initial login as a sequence base. **Try next username** evaluates
   `<base>1`, `<base>2`, and so on without leaving the grid.
5. Allow an exact username override without changing that sequence base.
6. Keep the eight most recent evaluations (username, value, reason). Clicking a
   history row freshly evaluates that exact key and resets the grid.
7. Count **unique** usernames evaluated this session (latest result if a name
   is revisited). Show green count, none count, `n`, and observed green
   percent next to the configured 30%. Do not treat a small sample as proof
   the rollout is wrong.

History records the value seen at that time. Assignment is stable while flag
configuration stays unchanged; changing rollout weights can move contexts
across the rollout boundary.

## Demo script

1. Provision (`rest/` / `terraform/`). Confirm default rule is 30% / 70%.
2. Log in as `alice`. Note highlight vs none.
3. Click **Try alice1**, then continue until history contains both `none` and
   `green` (the exact number of tries is not guaranteed).
4. Click an older history row. It re-evaluates the exact key and returns to the
   same assignment while weights are unchanged.
5. Type any exact username in the override field. The next generated username
   still follows the original `aliceN` sequence.
6. Optional: REST/lab control to set 0% or 100% so the whole class sees one
   side, then restore 30/70.

## Out of scope

Progressive stages, guarded rollouts, experiments, scheduled changes, and the
client SDK.
