# Create and Evaluate Flag Use Case

This document defines **11-create-eval-flag** under [99-use-cases](../README.md).

## Goal

Introduce **one LaunchDarkly flag** end to end: create it, evaluate it in the grid navigator, and change what users see by toggling the flag in the LaunchDarkly UI or with a REST API call.

This is the smallest use case in the repository — no segments, no percentage rollouts, no experiment utilities. The focus is understanding **flag state** (on/off) and **variation value** (highlight color).

Baseline grid navigator behavior is defined in [00-reference-code/application.md](../../00-reference-code/application.md).

## Flag

Single string multivariate flag for selected-cell highlight color:

| Key | `configure-grid-selection-green-highlight` |
|-----|-------------------------------------------|
| Type | **String** |
| Default (off) | `"none"` — no highlight colors |

| Variation | Application behavior |
|-----------|----------------------|
| `none` | Selected cell and username match 00-reference-code (`X` only, no colors) |
| `green` | Green highlight on selected cell and username |
| `yellow` | Yellow highlight |
| `red` | Red highlight |
| `blue` | Blue highlight |
| `purple` | Purple highlight |

Variations match the string highlight flag used in [02-segments-by-name](../02-segments-by-name/application.md). This use case does **not** add segment targeting — all users receive the **fallthrough** variation when the flag is on.

> **Note:** [10-flag-enablement](../../10-flag-enablement/) uses the same key as a **boolean** flag. Use a dedicated environment if you run multiple examples in one project.

### Provisioning default

After [terraform/](terraform/) or [rest/](rest/) provisioning:

- Flag exists with six string variations
- Flag is **off** in the target environment
- Off variation is `none`

When **on**, the fallthrough rule serves one color variation to every user context (default after `./turn-flag-on.sh`: `green`).

## Application behavior

1. User logs in with a username (LaunchDarkly context key)
2. Application evaluates `configure-grid-selection-green-highlight` for that user
3. Header shows **`Name: {username} ({color-label})`** — label is `(no-color)` when variation is `none`
4. Selected grid cell uses the same highlight color (colored `X` outline in console)
5. Standard 00-reference-code navigation, logout (`L`), quit (`Q`)
6. Re-evaluates the flag periodically so UI changes appear without restarting the app

### Single-evaluation mode

`11-create-eval-flag.py --evaluate-once <username>` prints JSON with `highlightColor`, `flagValue`, and `colorLabel`, then exits.

Add `--verbose` to include SDK initialization state and evaluation reason.

## What you should see

| Flag state | Fallthrough | Selected cell | Username in header |
|------------|-------------|---------------|-------------------|
| **Off** | (ignored) | Plain `X`, no color | Plain text, `(no-color)` |
| **On** | `green` | Green `X` | Green text, `(green)` |
| **On** | `red` | Red `X` | Red text, `(red)` |

Toggling the flag or changing fallthrough in LaunchDarkly (UI or REST) updates what the SDK returns on the next evaluation.

## Acceptance criteria

- [ ] Provisioning creates the string flag and leaves it **off** with off variation `none`
- [ ] Console app runs with `LD_SDK_KEY` and shows no highlight when flag is off
- [ ] Turning flag **on** with fallthrough `green` colors the selected cell and username green
- [ ] `./set-highlight-color.sh red` changes highlight to red without restarting the app
- [ ] Turning flag **off** returns to 00-reference-code styling (`none`)
- [ ] `--evaluate-once` prints the resolved variation as JSON
- [ ] Language implementations in [python-console/](python-console/), [python/](python/), [node-console/](node-console/), [node/](node/), [java-console/](java-console/), [java/](java/), [go/](go/), [rust/](rust/), [cpp/](cpp/) behave consistently

## Further reading

- [README.md](README.md) — step-by-step UI and curl toggle walkthrough
- [02-segments-by-name/application.md](../02-segments-by-name/application.md) — same flag key with segment targeting
- [10-flag-enablement/application.md](../../10-flag-enablement/application.md) — boolean highlight flag reference
