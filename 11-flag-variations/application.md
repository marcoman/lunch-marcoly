# Flag Variations Application Specification

This document defines the feature flags and their **desired effects** for the **11-flag-variations** example.

Baseline grid navigator behavior (login, grid layout, navigation, header fields, session control, and selection styling) is defined in [00-reference/application.md](../00-reference/application.md). Implementations in this folder start from that baseline and add LaunchDarkly flag evaluation demonstrating **four variation types**: anonymous context, string, number, and JSON.

Repository layout and provisioning conventions are in [project.md](../project.md).

## Overview

**11-flag-variations** extends the reference grid navigator with four flags — one per LaunchDarkly multivariate type (plus anonymous context for the boolean flag). Unlike [10-flag-enablement](../10-flag-enablement/), this example does **not** include highlight or cohort flags; it focuses on variation types and their runtime effects.

| Flag key | Variation type | Purpose |
|----------|----------------|---------|
| `show-anonymous-host-os-emoji` | Boolean (anonymous context) | OS emoji before username using an anonymous evaluation context |
| `configure-navigation-count-label` | String | Label text for the navigation move counter |
| `configure-lucky-number` | Number | Lucky number shown in the header |
| `configure-max-navigation-moves` | JSON | Maximum allowed navigation moves per session |

Flags are provisioned in [terraform/](terraform/) and [rest/](rest/). Application code evaluates them at runtime using the LaunchDarkly SDK for each language.

## Relationship to other examples

| Aspect | 00-reference | 10-flag-enablement | 11-flag-variations |
|--------|--------------|--------------------|--------------------|
| LaunchDarkly | None | Boolean flags + private attributes | String, number, JSON, anonymous context |
| Baseline behavior | Full spec | Inherits from 00-reference | Inherits from 00-reference |
| Selected cell styling | `X` only | Optional colored highlight | `X` only (matches 00-reference) |
| Move count | Not present | Boolean show/hide + `Count: N` | Always visible as `{label}: N` (string label) |
| Header extras | Name, Current, Previous | Cohort label, optional count, optional emoji | Lucky number, optional anonymous OS emoji |
| Move limit | None | None | JSON `maxMoves` caps successful moves |

When a flag uses its **default variation**, behavior must match [00-reference/application.md](../00-reference/application.md) for the aspect that flag controls (except the move counter is always shown with the default label `Count`).

## Flag naming

Names and keys follow [LaunchDarkly flag conventions](https://launchdarkly.com/docs/guides/flags/flag-conventions): **action: subject** for the display name, **kebab-case** for the key.

---

## Flag 1: Anonymous host OS emoji

Demonstrates evaluation with an **anonymous** LaunchDarkly context and a **private** `hostOs` attribute — the same OS detection and emoji mapping as [10-flag-enablement/application.md](../10-flag-enablement/application.md#flag-4-host-os-emoji-private-attribute), but the flag is evaluated against an anonymous context rather than the logged-in username context.

### Metadata

| Attribute | Value |
|-----------|-------|
| **Kind** | Show (temporary) |
| **Name** | `Show: anonymous host OS emoji` |
| **Key** | `show-anonymous-host-os-emoji` |
| **Temporary** | Yes |
| **Tags** | `grid-navigator`, `show`, `header`, `anonymous`, `private-attributes` |
| **Variation type** | Boolean |
| **Default variation (off)** | `false` (Hidden) |
| **SDK default when offline** | `false` — no emoji |

### Anonymous evaluation context

This flag **must** be evaluated with a dedicated anonymous context, separate from the logged-in user context used for other flags:

| Context field | Value |
|---------------|-------|
| `key` | Stable anonymous key (e.g. `anonymous` or a session-scoped UUID) |
| `anonymous` | `true` |
| `hostOs` | Detected host OS (`linux`, `macos`, `windows`, `other`) — **private** |

Other flags (string, number, JSON) use the **logged-in username** as the context key.

### Emoji mapping

Same as 10-flag-enablement:

| `hostOs` | Emoji |
|----------|-------|
| `linux` | 🐧 |
| `macos` | 🍎 |
| `windows` | 🪟 |
| `other` | 😊 |

### Desired effects

#### When `false` (default)

- Header name line shows the username only: `Name: alice`
- No emoji appears

#### When `true`

- Header name line shows **`emoji username`**: e.g. `Name: 🍎 alice` on macOS
- Emoji is evaluated using the **anonymous** context with private `hostOs`

---

## Flag 2: Navigation count label (string)

Replaces the boolean show/hide count from 10-flag-enablement with a **string** flag that controls the **label text** for the move counter. The counter is always visible; only the label prefix changes.

### Metadata

| Attribute | Value |
|-----------|-------|
| **Kind** | Configure (operational) |
| **Name** | `Configure: navigation count label` |
| **Key** | `configure-navigation-count-label` |
| **Temporary** | No |
| **Tags** | `grid-navigator`, `configure`, `header`, `string` |
| **Variation type** | String |
| **Default variation** | `"Count"` |
| **SDK default when offline** | `"Count"` |

### Variations

| Value | Label | Header display |
|-------|-------|----------------|
| `"Count"` | Count | `Count: N` |
| `"Move Count"` | Move Count | `Move Count: N` |
| `"Moves"` | Moves | `Moves: N` |
| `"Navigation Counts"` | Navigation Counts | `Navigation Counts: N` |

### Desired effects

- The header **always** displays a move counter line: **`{label}: N`**
- `N` is the number of **successful navigation moves** since the grid screen loaded (starts at `0`)
- Boundary keypresses that do not change position do **not** increment `N`
- Logout resets `N` to `0`; the label is re-evaluated on the next login
- Default label is **`Count`** → `Count: 0` on first render

---

## Flag 3: Lucky number (number)

A **number** flag whose value is displayed in the header.

### Metadata

| Attribute | Value |
|-----------|-------|
| **Kind** | Configure (operational) |
| **Name** | `Configure: lucky number` |
| **Key** | `configure-lucky-number` |
| **Temporary** | No |
| **Tags** | `grid-navigator`, `configure`, `header`, `number` |
| **Variation type** | Number |
| **Default variation** | `0` |
| **SDK default when offline** | `0` |

### Variations

| Value | Label |
|-------|-------|
| `0` | Zero (default) |
| `1` | One |
| `2` | Two |
| `3` | Three |
| `4` | Four |
| `5` | Five |

### Desired effects

- The header displays **`Lucky Number is: N`** where `N` is the flag's numeric variation
- Default: **`Lucky Number is: 0`**
- The lucky number does not affect navigation or move limits
- Re-evaluate on flag change (streaming or poll) without requiring a move

---

## Flag 4: Maximum navigation moves (JSON)

A **JSON** flag that limits how many successful navigation moves are allowed per grid session.

### Metadata

| Attribute | Value |
|-----------|-------|
| **Kind** | Configure (operational) |
| **Name** | `Configure: max navigation moves` |
| **Key** | `configure-max-navigation-moves` |
| **Temporary** | No |
| **Tags** | `grid-navigator`, `configure`, `navigation`, `json` |
| **Variation type** | JSON |
| **Default variation** | `{"maxMoves": 100}` |
| **SDK default when offline** | `{"maxMoves": 100}` |

### Variations

| Value | Label | Meaning |
|-------|-------|---------|
| `{"maxMoves": 100}` | Standard (100) | Default limit for standard users |
| `{"maxMoves": 10}` | Limited (10) | Short limit for testing |
| `{"maxMoves": 1000}` | Extended (1000) | High limit |

### Desired effects

- Parse `maxMoves` from the JSON variation (integer ≥ 0)
- **Standard users** (default): **100** total successful moves allowed per grid session
- When `moveCount >= maxMoves`, further navigation keypresses that would change position are **ignored** (position unchanged, `N` unchanged, previous unchanged)
- Boundary keypresses at the edge continue to be ignored as in 00-reference (they never increment `N`)
- The counter still displays `{label}: N` showing how many moves have been used
- Logout resets `moveCount` to `0`; the limit is re-evaluated on next login

Example header after 100 moves with default flags:

```text
Name: alice
Current position: b/r
Previous position: b/m
Count: 100
Lucky Number is: 0
```

---

## State model

Implementations should model at least the 00-reference state **plus**:

| State | Type | Notes |
|-------|------|-------|
| `moveCount` | integer | Starts at `0`; increments on successful moves |
| `countLabel` | string | From `configure-navigation-count-label` |
| `luckyNumber` | number | From `configure-lucky-number` |
| `maxMoves` | integer | Parsed from `configure-max-navigation-moves` JSON |
| `osEmoji` | string | From anonymous flag evaluation, or empty |

```text
position = { row: "t" | "m" | "b", col: "l" | "m" | "r" }
```

Refresh flag values when the LaunchDarkly SDK reports a change (streaming) or on each render/poll if streaming is not used.

## API response shape (web implementations)

`GET /api/flags?username=...` returns:

```json
{
  "countLabel": "Count",
  "luckyNumber": 0,
  "maxMoves": 100,
  "osEmoji": "🍎"
}
```

## Acceptance criteria

An implementation in **11-flag-variations** is correct when it satisfies all [00-reference acceptance criteria](../00-reference/application.md#acceptance-criteria) **and**:

### Flag 1 — anonymous OS emoji

1. With the flag **off**, no emoji appears before the username
2. With the flag **on**, the correct emoji appears for the detected host OS
3. The flag is evaluated with an **anonymous** context (`anonymous: true`) and private `hostOs`

### Flag 2 — string count label

4. Default label is `Count` → header shows `Count: N`
5. When the flag returns `"Moves"`, header shows `Moves: N`
6. Move count increments only on successful moves; boundary presses do not increment

### Flag 3 — lucky number

7. Default shows `Lucky Number is: 0`
8. When the flag returns `3`, header shows `Lucky Number is: 3`

### Flag 4 — JSON move limit

9. Default `maxMoves` is **100** for standard users
10. When `moveCount` reaches `maxMoves`, navigation that would change position is blocked
11. Move counter reflects actual successful moves (may reach `maxMoves` and stop)

### Provisioning alignment

12. Flag keys in code match [terraform/main.tf](terraform/main.tf) and [rest/](rest/) exactly:

```text
show-anonymous-host-os-emoji
configure-navigation-count-label
configure-lucky-number
configure-max-navigation-moves
```

## Further reading

- [README.md](README.md) — example overview and provisioning links
- [00-reference/application.md](../00-reference/application.md) — baseline grid navigator behavior
- [10-flag-enablement/application.md](../10-flag-enablement/application.md) — boolean flags and host OS emoji reference
- [Flag conventions](https://launchdarkly.com/docs/guides/flags/flag-conventions) — naming and tagging guidance
- [Multivariate flags](https://launchdarkly.com/docs/sdk/features/flag-types) — string, number, and JSON variation types
