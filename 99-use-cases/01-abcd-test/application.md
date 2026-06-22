# ABCD Test Use Case

This document defines the **01-abcd-test** use case under [99-use-cases](../README.md).

## Goal

Demonstrate an **A-B-C-D test** using LaunchDarkly: four string variations of `configure-navigation-count-label` are served in controlled proportions when the flag is **on**. When the flag is **off**, all users see the default label `Count`.

Baseline grid navigator behavior is defined in [00-reference/application.md](../../00-reference/application.md).

## Flag

Uses the same key and variations as [11-flag-variations](../../11-flag-variations/application.md#flag-2-navigation-count-label-string):

| Key | `configure-navigation-count-label` |
|-----|-----------------------------------|
| Type | String |
| Default (off) | `"Count"` |

| Variation | Header line |
|-----------|-------------|
| A — `"Count"` | `Count: N` |
| B — `"Move Count"` | `Move Count: N` |
| C — `"Moves"` | `Moves: N` |
| D — `"Navigation Counts"` | `Navigation Counts: N` |

### Provisioning default

The flag is **off** in the target environment after provisioning. With the flag off, every evaluation returns the off variation (`"Count"`).

### Experiment mode

When the flag is **on** with a percentage rollout on the fallthrough rule, LaunchDarkly assigns each **unique username context** to a variation according to the configured weights. The default experiment allocation is an **equal split**: 25%, 25%, 25%, 25%.

## Application behavior

The console application embeds the LaunchDarkly server SDK:

1. User logs in with a username (context key)
2. On grid load, evaluate `configure-navigation-count-label` for that user
3. Header displays **`{label}: N`** where `label` is the flag variation and `N` is successful move count
4. Standard 00-reference navigation, logout (`L`), and quit (`Q`)

### Single-evaluation mode

`01-abcd-test.py --evaluate-once <username>` prints the resolved label to stdout and exits. This is the path used by the experiment utility for each trial.

## Experiment utility

`01-abcd-test-experiment.py` exercises the ABCD test by:

1. Optionally configuring fallthrough percentage rollout via the REST API
2. Running the application once per trial with a unique username
3. Summarizing observed variations in a table

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--interactive` | off | Prompt to confirm or override each parameter |
| `--experiment-count` | `1000` | Number of trials |
| `--experiment-delay` | `1` | Delay between trials in milliseconds |
| `--experiment-allocation` | equal split | Comma-separated percentages per variation (must sum to 100) |
| `--experiment-seed` | random per run | Integer mixed into each trial username (`abcd-exp-{seed}-{i}`) |
| `--experiment-salt` | (none) | Optional extra string in each trial username for more variation |

### Deterministic rollout vs. experiment randomness

LaunchDarkly percentage rollout assigns variations **deterministically** from each context key. The same username always receives the same variation until rollout weights change. Without a seed, repeated experiment runs used identical usernames (`abcd-exp-0`, `abcd-exp-1`, …) and therefore produced **identical** count distributions every time.

`--experiment-seed` and `--experiment-salt` vary the context keys between runs while keeping trials independent within a run. Use a fixed seed to reproduce a run; omit it (default) for a new random seed each time. The chosen seed is printed before trials start.

### Equal allocation rule

When `--experiment-allocation` is omitted, percentages are split evenly with remainder assigned to the **last** variation:

| Variations | Default allocation |
|------------|-------------------|
| 4 | 25, 25, 25, 25 |
| 3 | 33, 33, 34 |
| 6 | 16, 16, 16, 16, 16, 20 |

Fractional values round **down** for all but the last slot; the last slot receives the remainder so the total is 100.

### Output

At completion, print a table:

```text
Variation              Count    Pct
Count                  248      24.8%
Move Count             253      25.3%
Moves                  251      25.1%
Navigation Counts      248      24.8%
Total                  1000
```

## Acceptance criteria

1. Flag defaults to **off** after provisioning; label is always `Count`
2. With flag **on** and equal rollout, four variation labels appear across distinct user contexts
3. Experiment utility runs `experiment-count` trials and prints variation counts
4. `--experiment-allocation` updates LaunchDarkly fallthrough weights before trials
5. Application matches 00-reference grid behavior aside from the count label line
