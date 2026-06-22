# Segments by Name Use Case

This document defines **02-segments-by-name** under [99-use-cases](../README.md).

## Goal

Demonstrate **LaunchDarkly segments** driven by **context attributes** the application supplies at login. Selection highlight color comes from the `configure-grid-selection-green-highlight` flag, targeted by segment membership rather than application-side color rules.

Baseline grid navigator behavior is defined in [00-reference/application.md](../../00-reference/application.md).

## Flag

Reuses the highlight flag key from [10-flag-enablement](../../10-flag-enablement/application.md):

| Key | `configure-grid-selection-green-highlight` |
|-----|-------------------------------------------|
| Type | **String** (this use case) |
| Default (off) | `"none"` — no highlight colors |

| Variation | Application behavior |
|-----------|----------------------|
| `none` | Selected cell and username match 00-reference (`X` only, no colors) |
| `yellow` | Yellow highlight |
| `red` | Red highlight |
| `blue` | Blue highlight |
| `green` | Green highlight |
| `purple` | Purple highlight |

> **Note:** In [10-flag-enablement](../../10-flag-enablement/), this key is a **boolean** flag. This use case provisions it as a **string** multivariate flag for segment targeting. Use a dedicated environment or project if both examples share an account.

### Provisioning default

Flag is **off** in the target environment after provisioning (`off` variation = `none`).

When **on**, segment-based targeting rules return the highlight color variation for each user context.

## Context attributes (application-supplied)

The application builds a **user** context (`key` = login username) with attributes segments match on. Evaluation follows **priority order**; once a rule matches, lower-priority attributes are not computed:

| Priority | Condition | Attributes set | Segment type |
|----------|-----------|----------------|--------------|
| 1 | Username is exactly `generic` (case-insensitive) | `generic=true`, `segmentType=generic` | **Generic** — stop |
| 2 | Username is exactly a color name | `namedColor={color}`, `segmentType=named-color` | **Named color** — stop |
| 3 | Even number of letters in username | `userKind=human` | (continues) |
| 3 | Odd number of letters in username | `userKind=robot` | (continues) |
| 4 | Username contains `beta` (case-insensitive) | `beta=true` | Combined with step 3 |

Color names: `yellow`, `red`, `blue`, `green`, `purple` (exact match, case-insensitive).

Letter count includes **alphabetic characters only** (`str.isalpha()`).

### Allowed segment types

| Segment type | Example usernames | Expected highlight (flag on) |
|--------------|-------------------|------------------------------|
| Generic | `generic` | `none` |
| Named color | `yellow`, `Red`, `purple` | that color |
| Human | `ab` (2 letters) | `yellow` |
| Robot | `alice` (5 letters) | `red` |
| Human + beta | `beta` (4 letters, contains beta) | `green` |
| Robot + beta | `abeta` (5 letters, contains beta) | `purple` |

Highlight colors for composite types (when flag targeting is provisioned):

| Segment type | Highlight color |
|--------------|-----------------|
| `human` | `yellow` |
| `robot` | `red` |
| `human-beta` | `green` |
| `robot-beta` | `purple` |

## Segments

Seven rule-based segments (provisioned in [terraform/](terraform/) and [rest/](rest/)):

| Segment key | Matches |
|-------------|---------|
| `seg-by-name-generic` | `segmentType` is `generic` |
| `seg-by-name-color-{color}` | `namedColor` is `{color}` |
| `seg-by-name-human` | `segmentType` is `human` |
| `seg-by-name-robot` | `segmentType` is `robot` |
| `seg-by-name-human-beta` | `segmentType` is `human-beta` |
| `seg-by-name-robot-beta` | `segmentType` is `robot-beta` |

Flag targeting rules (first match wins) map each segment to its highlight variation.

## Application behavior

1. User logs in with a username
2. Application builds LaunchDarkly context per rules above
3. Evaluate `configure-grid-selection-green-highlight` for that context
4. Header shows **`Name: {username} ({segment-label})`** with highlight color when not `none`
5. Selected grid cell uses the same highlight color
6. Standard 00-reference navigation, logout (`L`), quit (`Q`)

### Segment label format

| Type | Label example |
|------|---------------|
| Generic | `(generic)` |
| Named color | `(yellow)` |
| Human | `(human-yellow)` |
| Robot | `(robot-red)` |
| Human + beta | `(human-beta-green)` |
| Robot + beta | `(robot-beta-purple)` |
| No highlight (`none`) | `(no-color)` in label when variation is `none` |

## Acceptance criteria

1. Flag defaults to **off**; no highlight colors (00-reference styling)
2. With flag **on**, `generic` receives `none` variation
3. With flag **on**, color-name usernames receive matching color variation
4. With flag **on**, even/odd letter rules assign human/robot segments with correct colors
5. With flag **on**, `beta` substring adds beta segment (human-beta or robot-beta)
6. Context attributes match segment rules; application does not apply colors outside flag evaluation
7. Application matches 00-reference grid behavior aside from highlight and segment label
