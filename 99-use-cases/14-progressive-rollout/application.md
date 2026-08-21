# Progressive Rollout Use Case

This document defines **14-progressive-rollout** under [99-use-cases](../README.md).

## Goal

Release a **green grid highlight** to production gradually using a **progressive rollout** on a single string flag — `configure-grid-selection-green-highlight`.

> In this example, we have a progressive rollout over **15 minutes** in **five equal stages**: **10%**, **20%**, **40%**, **60%**, and **100%** of users receive the green highlight. Each stage lasts **3 minutes**.

Baseline grid navigator behavior is defined in [00-reference-code/application.md](../../00-reference-code/application.md).

## Flag

| Key | `configure-grid-selection-green-highlight` |
|-----|-------------------------------------------|
| Type | **String** |
| Off variation | `none` — no highlight |
| Rollout target | `green` — green highlight on selected cell and username |

This use case uses only the **`none`** and **`green`** variations for the rollout. Other color variations exist on the flag for consistency with [10-code-control/12-flag-variations](../../10-code-control/12-flag-variations/) but are not part of the rollout schedule.

### Rollout schedule

| Stage | Time (from start) | Green traffic |
|-------|-------------------|---------------|
| 1 | 0:00 – 3:00 | 10% |
| 2 | 3:00 – 6:00 | 20% |
| 3 | 6:00 – 9:00 | 40% |
| 4 | 9:00 – 12:00 | 60% |
| 5 | 12:00 – 15:00 | 100% |

LaunchDarkly buckets users by context key. As the percentage increases, more users receive `green`; users already in the green bucket keep it (sticky allocation).

### Provisioning default

After [terraform/](terraform/) or [rest/](rest/) provisioning:

- Flag exists with string variations including `none` and `green`
- Flag is **off** in the target environment
- Off variation is `none`

## Application behavior

Same as [11-create-eval-flag](../11-create-eval-flag/application.md):

1. User logs in with a username (LaunchDarkly context key)
2. Application evaluates `configure-grid-selection-green-highlight`
3. Header shows `Name: {username} ({color-label})` and `Flag value:`
4. Selected grid cell uses the resolved highlight color
5. Re-evaluates every 500 ms in console apps

During an active rollout, different usernames may receive `green` or `none` depending on their bucket and the current rollout percentage.

### Single-evaluation mode

`14-progressive-rollout.py --evaluate-once <username>` prints JSON with `highlightColor`, `flagValue`, and `colorLabel`.

### Monitor script

[14-progressive-rollout-monitor.py](14-progressive-rollout-monitor.py) samples 20 evaluations every 30 seconds, queries LaunchDarkly for the current rollout stage, and prints observed green vs none percentages.

- With a **UI progressive rollout**, LaunchDarkly auto-advances stages; the monitor reports `progressive stage N`.
- With **`./rest/start-progressive-rollout.sh`**, stages are simulated via REST percentage updates; the monitor reports `simulated stage N — REST percentage`.
- If a **guarded rollout** (`measuredRollout`) is active, the monitor warns to use [15-guarded-rollout](../15-guarded-rollout/) instead.

## Acceptance criteria

- [ ] Provisioning creates the string flag and leaves it **off**
- [ ] `./rest/configure-progressive-rollout.sh` prepares the flag and emits targeting JSON for a UI progressive rollout
- [ ] `./rest/get-progressive-rollout.sh` detects `progressiveRollout` / `progressiveRolloutConfig` (and warns on `measuredRollout`)
- [ ] `./rest/start-progressive-rollout.sh` advances through 10/20/40/60/100% over 15 minutes (simulated percentages)
- [ ] `./rest/set-rollout-percent.sh 40` sets a 40% green / 60% none fallthrough rollout
- [ ] Monitor script reports batch results with inline countdown between runs
- [ ] Console app shows green highlight for users in the green bucket
- [ ] `./rest/stop-rollout.sh` turns flag off — all users receive `none`
- [ ] Language implementations behave consistently with `--evaluate-once`

## Further reading

- [README.md](README.md) — quick start, UI/curl walkthrough, monitor script
- [11-create-eval-flag](../11-create-eval-flag/) — single-variation fallthrough (no rollout)
- [01-abcd-test](../01-abcd-test/) — static percentage rollout across four label variations
- [Progressive rollouts](https://launchdarkly.com/docs/home/releases/progressive-rollouts)
