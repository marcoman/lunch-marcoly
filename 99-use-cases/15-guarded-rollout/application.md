# Guarded Rollout Use Case

This document defines **15-guarded-rollout** under [99-use-cases](../README.md).

## Goal

Release a **green grid highlight** to production gradually using a **guarded rollout** on a single string flag — `configure-grid-selection-green-highlight`, with simulated guardrail metrics in the application and test harness.

> In this example, we have a guarded rollout over **12 minutes** in **four equal stages**: **10%**, **20%**, **30%**, and **50%** of users receive the green highlight. Each stage lasts **3 minutes**.

Baseline grid navigator behavior is defined in [00-reference/application.md](../../00-reference/application.md).

## Flag

| Key | `configure-grid-selection-green-highlight` |
|-----|-------------------------------------------|
| Type | **String** |
| Off variation | `none` — no highlight |
| Rollout target | `green` — green highlight on selected cell and username |

### Rollout schedule

| Stage | Time (from start) | Green traffic |
|-------|-------------------|---------------|
| 1 | 0:00 – 3:00 | 10% |
| 2 | 3:00 – 6:00 | 20% |
| 3 | 6:00 – 9:00 | 30% |
| 4 | 9:00 – 12:00 | 50% |

### Guardrail metrics

Configure these three metrics in LaunchDarkly for the guarded rollout. The application and test harness simulate the underlying signals:

| Metric | Simulated signal | Threshold | Failure condition |
|--------|------------------|-----------|-------------------|
| **Latency** | Random 0–1000 ms delay on navigation when flag serves `green` | 200 ms | >10% of navigations exceed 200 ms |
| **Error rate** | 5% chance of incorrect highlight color when flag serves `green` | 0% | Any incorrect color |
| **Movement** | Test harness navigates 5 times per exercise | 1 navigation | Fewer than 1 navigation (5% of tests skip) |

Guardrails apply only when the SDK returns **`green`** for the user context. When the flag is off or serves `none`, navigation is immediate and colors are always correct.

### Provisioning default

After [terraform/](terraform/) or [rest/](rest/) provisioning:

- Flag exists with string variations including `none` and `green`
- Flag is **off** in the target environment
- Off variation is `none`

## Application behavior

1. User logs in with a username (LaunchDarkly context key)
2. Application evaluates `configure-grid-selection-green-highlight`
3. Header shows `Name:`, `Flag value:`, positions
4. When flag serves **`green`**:
   - Each navigation waits a random **0–1000 ms** before updating the display
   - **5%** of navigations may show an incorrect highlight color on the selected cell
5. Standard 00-reference navigation, logout (`L`), quit (`Q`)
6. Re-evaluates the flag every 500 ms in console apps

### Exercise mode (test harness)

`15-guarded-rollout.py --exercise-once <username>` simulates **5 navigations** and returns JSON:

```json
{
  "username": "guard-probe-001-00",
  "highlightColor": "green",
  "navigations": 5,
  "latencyMs": [45, 320, 890, 12, 150],
  "latencyFailures": 2,
  "latencyFailure": true,
  "colorErrors": 1,
  "errorRateFailure": true,
  "movementFailure": false,
  "skippedNavigation": false
}
```

`--skip-navigation` simulates a user who never moves (movement guardrail failure).

### Single-evaluation mode

`--evaluate-once <username>` prints flag evaluation JSON only (no guardrail simulation).

## Acceptance criteria

- [ ] Provisioning creates the string flag and leaves it **off**
- [ ] `./rest/start-guarded-rollout.sh` advances through 10/20/30/50% over 12 minutes (simulated percentages)
- [ ] `./rest/get-guarded-rollout.sh` reports active guarded rollout when configured in the UI
- [ ] Monitor script detects guarded rollout via `expand=guardedRollout`
- [ ] Python console applies latency delay and occasional color errors when flag serves `green`
- [ ] `--exercise-once` returns guardrail metrics JSON
- [ ] Monitor script runs 20 exercises per batch, 5% skip navigation, reports metric failures
- [ ] `./rest/stop-rollout.sh` turns flag off
- [ ] Language implementations support `--evaluate-once` consistently

## Further reading

- [README.md](README.md) — quick start, UI/curl walkthrough, monitor script
- [14-progressive-rollout](../14-progressive-rollout/) — same schedule without guardrails
- [Guarded rollouts](https://launchdarkly.com/docs/home/releases/guarded-rollouts)
