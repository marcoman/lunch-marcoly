# Flag Enablement Application Specification

This document defines the feature flags and their **desired effects** for the **10-flag-enablement** example.

Baseline grid navigator behavior (login, grid layout, navigation, header fields, and selection styling) is defined in [00-reference/application.md](../00-reference/application.md). Implementations in this folder start from that baseline and add LaunchDarkly flag evaluation on top.

Repository layout and provisioning conventions are in [project.md](../project.md).

## Overview

**10-flag-enablement** extends the reference grid navigator with four boolean feature flags. All flags apply to every language implementation in this folder (web and console).

| Flag key | Purpose |
|----------|---------|
| `configure-grid-selection-green-highlight` | Enable or disable colored highlight on the selected cell |
| `configure-grid-selection-context-highlight` | Enable context-based highlight colors derived from the login name |
| `show-navigation-move-count` | Show or hide a navigation counter in the header |
| `show-host-os-emoji` | Show or hide a host OS emoji before the username (private `hostOs` attribute) |

Flags are provisioned in [terraform/](terraform/) and [rest/](rest/). Application code evaluates them at runtime using the LaunchDarkly SDK for each language.

## Relationship to 00-reference

| Aspect | 00-reference | 10-flag-enablement |
|--------|--------------|-------------------|
| LaunchDarkly | None | Required |
| Baseline behavior | Full spec | Inherits from 00-reference |
| Selected cell styling | `X` only — no colors | `X` by default; colored highlight when highlight flag is on |
| Header Name field | Plain username | `emoji username` when OS flag on; username colored when highlight is on |
| Header fields | Name, Current position, Previous position | Same three fields, plus optional Count |
| Navigation counter | Not present | Controlled by show flag |
| Screen background | Light (web) / default terminal | Dark background for contrast with light and dark highlight colors |

When a flag is **off** (default), behavior must match [00-reference/application.md](../00-reference/application.md) for the aspect that flag controls.

## Flag naming

Names and keys follow [LaunchDarkly flag conventions](https://launchdarkly.com/docs/guides/flags/flag-conventions): **action: subject** for the display name, **kebab-case** for the key.

The first highlight flag retains the historical key `configure-grid-selection-green-highlight` even though the default highlight color is now **pink**.

---

## Flag 1: Selection highlight on selected cell

### Metadata

| Attribute | Value |
|-----------|-------|
| **Kind** | Configure (operational) |
| **Name** | `Configure: grid selection green highlight` |
| **Key** | `configure-grid-selection-green-highlight` |
| **Temporary** | No — long-lived styling configuration |
| **Tags** | `grid-navigator`, `configure`, `ui` |
| **Default variation (off)** | `false` (`X only`) |
| **SDK default when offline** | `false` — match 00-reference (`X` only, no colors) |

### Variations

| Value | Label | Application behavior |
|-------|-------|----------------------|
| `true` | Highlight enabled | Selected cell shows **`X` with a colored highlight** — background (web) or colored outline (console) |
| `false` | X only | Selected cell shows **`X` only** — no colors; same as [00-reference/application.md](../00-reference/application.md#presentation) |

### Desired effects

#### When `false` (default, flag off)

Behavior matches 00-reference exactly:

- **Web:** selected cell uses the same styling as unselected cells (dark theme); `X` is centered in the cell
- **Console:** selected cell uses default terminal styling on the dark screen background; `X` is visible in the cell
- Username in the header is not colored; no cohort label appears
- Unselected cells are empty (no marker)

#### When `true` (flag on)

Colored highlight is added to the selected cell:

- **Default color (context flag off):** **pink**
- **Context color (context flag on):** determined by username cohort rules (see Flag 2)
- **Web:** selected cell uses the resolved background color with appropriate foreground contrast; unselected cells use the dark grid cell background
- **Console:** selected cell outline uses the resolved ANSI color; screen uses a dark background (`#236` gray or equivalent) for contrast
- Header **username** uses the same color as the selection highlight
- When the context flag is on and cohort words are detected, a **cohort label** appears in parentheses after the username (see Flag 2)
- Header fields, navigation rules, and grid layout are otherwise unchanged

#### What this flag does not change

- Login screen
- Grid size, starting position (`m/m`), or edge behavior
- Header fields Current position, Previous position (values unchanged)
- Navigation move count visibility (see Flag 3)
- Cohort parsing rules (see Flag 2) — this flag only enables/disables highlight styling

### Evaluation

Evaluate this flag when rendering the grid and header (and on flag change if the SDK supports streaming). Re-render styling when the variation changes without requiring a navigation move.

Use the logged-in username as the LaunchDarkly evaluation context key.

---

## Flag 2: Context-based highlight colors

### Metadata

| Attribute | Value |
|-----------|-------|
| **Kind** | Configure (operational) |
| **Name** | `Configure: grid selection context highlight` |
| **Key** | `configure-grid-selection-context-highlight` |
| **Temporary** | No |
| **Tags** | `grid-navigator`, `configure`, `ui`, `context` |
| **Default variation (off)** | `false` (`Default pink`) |
| **SDK default when offline** | `false` — use pink when highlight flag is on |

### Variations

| Value | Label | Application behavior |
|-------|-------|----------------------|
| `true` | Context colors | Parse cohort words from the login name and apply cohort color rules |
| `false` | Default pink | When highlight flag is on, use **pink** for selection and username |

### Cohort detection

Cohort membership is determined by **substring match** (case-insensitive) on the login name:

| Word in login name | Cohort |
|--------------------|--------|
| `human` | human |
| `robot` | robot |
| `beta` | beta |

A user may belong to multiple cohorts. Examples:

| Login name | Detected cohorts | Cohort label |
|------------|------------------|--------------|
| `human` | human | `(human-yellow)` |
| `robot` | robot | `(robot-red)` |
| `beta-user` | beta | `(beta-blue)` |
| `99human88betazoid` | human, beta | `(human-beta-green)` |
| `robot-beta` | robot, beta | `(robot-beta-purple)` |
| `alice` (context on) | none | `(pink)` |
| any (highlight off) | — | `(no-color)` |
| any (highlight on, context off) | — | `(pink)` |

The cohort label is shown in parentheses immediately after the username in the header. It always includes the resolved color name (`no-color` when highlight is off, otherwise `pink`, `yellow`, `red`, `blue`, `green`, or `purple`). Cohort identifiers (`human`, `robot`, `beta`) appear before the color when the context flag is on and matching words are found in the login name.

The label uses the **same foreground color** as the username and highlight when highlight is on; when highlight is off, the label uses default text styling.

### Color rules

When **both** the highlight flag and this flag are **on**, apply the first matching rule:

| Condition | Highlight & username color |
|-----------|---------------------------|
| human **and** beta | **green** |
| robot **and** beta | **purple** |
| human only | **yellow** |
| robot only | **red** |
| beta only | **blue** |
| no cohort words matched | **pink** (same as context flag off) |

When the highlight flag is **on** and this flag is **off**, color is always **pink** and the label is `(pink)`.

When the highlight flag is **off**, no colors appear on the username or selection; the label is `(no-color)`.

### Desired effects

#### When `false` (default)

- With highlight flag on: pink selection highlight; username in pink; no `(cohort)` label
- With highlight flag off: matches 00-reference

#### When `true`

- With highlight flag on: selection highlight, username, and cohort label use the resolved cohort color
- Cohort identifiers in the label appear only when the context flag is on and at least one cohort word is detected
- With highlight flag off: the label is `(no-color)` with no username or cell coloring

### Evaluation

Evaluate on each render together with Flag 1. Cohort parsing is **application logic** applied after flag evaluation; the flag gates whether cohort rules run or pink is used.

---

## Flag 3: Navigation move count in header

### Metadata

| Attribute | Value |
|-----------|-------|
| **Kind** | Show (temporary) |
| **Name** | `Show: navigation move count` |
| **Key** | `show-navigation-move-count` |
| **Temporary** | Yes — remove when no longer needed |
| **Tags** | `grid-navigator`, `show`, `header` |
| **Default variation (off)** | `false` (`Hidden`) |
| **SDK default when offline** | `false` — do not display the count |

### Variations

| Value | Label | Application behavior |
|-------|-------|----------------------|
| `true` | Visible | Header displays **`Count: N`** |
| `false` | Hidden | Count is not shown anywhere in the UI |

### Desired effects

#### When `false` (default, flag off)

- The header shows only the three fields from 00-reference: **Name**, **Current position**, **Previous position** (plus optional cohort label when highlight flags dictate)
- No count label, value, or placeholder appears in the header

#### When `true` (flag on)

- The header adds a fourth field: **`Count: N`**
- `N` is the number of **successful navigation moves** since the grid screen loaded
- `N` starts at **`0`** when the grid screen first appears (after login)
- `N` increments by **`1`** on each move that changes the current position
- Boundary keypresses that leave the position unchanged do **not** increment `N`
- The count persists for the session; returning to the login screen and re-entering resets `N` to `0`

Example header with all flags on, user `99human88betazoid`, after two moves:

```text
Name: 99human88betazoid (human-beta-green)    ← username and label in green
Current position: t/m
Previous position: m/m
Count: 2
```

#### What this flag does not change

- Login screen
- Grid layout, navigation rules, or selection/username styling
- How Name, Current position, or Previous position are computed
- Highlight or cohort colors (see Flags 1 and 2)

### Evaluation

Evaluate this flag when rendering the header (and on flag change if the SDK supports streaming). Toggling the flag on or off should show or hide the Count field on the next render without requiring a navigation move.

The move counter is **application state**, not a flag variation. The flag only controls **visibility** of the count the app already tracks.

---

## Flag 4: Host OS emoji (private attribute)

### Metadata

| Attribute | Value |
|-----------|-------|
| **Kind** | Show (temporary) |
| **Name** | `Show: host OS emoji` |
| **Key** | `show-host-os-emoji` |
| **Temporary** | Yes |
| **Tags** | `grid-navigator`, `show`, `header`, `private-attributes` |
| **Default variation (off)** | `false` (`Hidden`) |
| **SDK default when offline** | `false` — no emoji |

### Private context attribute

Each evaluation context includes a **`hostOs`** attribute set from the **host operating system** where the app runs. The attribute is marked **private** so the SDK uses it for targeting but does not send its value back to LaunchDarkly in events.

| Detected OS | `hostOs` value |
|-------------|----------------|
| Linux | `linux` |
| macOS | `macos` |
| Windows | `windows` |
| Other | `other` |

Implementations detect OS at runtime (e.g. `platform.system()` in Python, `runtime.GOOS` in Go). See [Private attributes](https://launchdarkly.com/docs/sdk/features/private-attributes) for SDK configuration.

### Variations

| Value | Label | Application behavior |
|-------|-------|----------------------|
| `true` | Visible | Display an OS emoji immediately before the username |
| `false` | Hidden | No emoji (default) |

### Emoji mapping

| `hostOs` | Emoji |
|----------|-------|
| `linux` | 🐧 (penguin) |
| `macos` | 🍎 (apple) |
| `windows` | 🪟 (window) |
| `other` | 😊 (smiley) |

### Desired effects

#### When `false` (default)

- Header name line shows the username only (plus cohort label when applicable): `Name: alice (no-color)`
- No emoji appears

#### When `true`

- Header name line shows **`emoji username`** (no brackets): e.g. `Name: 🍎 alice (no-color)` on macOS
- Emoji appears **before** the username; cohort label still follows the username
- Emoji is **not** colored by highlight styling (only the username and cohort label use highlight colors)

Example on Linux with highlight flags on for user `human`:

```text
Name: 🐧 human (human-yellow)
```

#### What this flag does not change

- Login screen
- Grid layout or navigation
- Highlight colors or cohort labels (see Flags 1 and 2)
- Move count visibility (see Flag 3)

### Evaluation

Evaluate when rendering the header. The app always attaches private `hostOs` to the LaunchDarkly context; the flag only controls whether the emoji is displayed.

---

## Visual design: dark background for contrast

Highlight colors include both **light** (yellow) and **dark** (purple, red, blue) tones. Implementations use a **dark screen background** so all cohort colors remain readable:

| Surface | Web | Console |
|---------|-----|---------|
| Page / screen background | `#1e1e2e` | ANSI `48;5;236` (dark gray) or black |
| Grid cell (unselected) | `#2d2d3d` | default on dark background |
| Body text | `#e8e8ec` | default light on dark |

Per-color styling (web examples):

| Color | Cell background | Cell text | Username text |
|-------|-----------------|-----------|---------------|
| pink | `#e91e63` | `#fff` | `#f48fb1` |
| yellow | `#fdd835` | `#1a1a1a` | `#fff176` |
| red | `#e53935` | `#fff` | `#ef5350` |
| blue | `#1e88e5` | `#fff` | `#64b5f6` |
| green | `#43a047` | `#fff` | `#81c784` |
| purple | `#8e24aa` | `#fff` | `#ce93d8` |

Console implementations use the closest ANSI foreground colors for username, cohort label, and cell outline.

---

## Combined behavior

All three flags are independent. Key combinations:

| Highlight | Context | Count | Result |
|-----------|---------|-------|--------|
| off | * | off | `(no-color)` label; 00-reference cell styling |
| off | * | on | `(no-color)` label; `Count: N` in header |
| on | off | off | Pink highlight + `X`; label `(pink)` |
| on | on | off | Cohort-based colors; label like `(human-yellow)` |
| on | on | on | Cohort colors + `Count: N` |

## State model

Implementations should model at least the 00-reference state **plus**:

| State | Type | Notes |
|-------|------|-------|
| `moveCount` | integer | Starts at `0` on grid screen load; increments on successful moves |
| `highlightEnabled` | boolean | From `configure-grid-selection-green-highlight` |
| `contextHighlight` | boolean | From `configure-grid-selection-context-highlight` |
| `showMoveCount` | boolean | From `show-navigation-move-count` |
| `highlightColor` | string | `none`, `pink`, `yellow`, `red`, `blue`, `green`, or `purple` — derived from flags + username |
| `cohortLabel` | string | e.g. `(human-beta-green)`, `(pink)`, or `(no-color)` |
| `osEmoji` | string | OS emoji character or empty string when flag is off |

```text
position = { row: "t" | "m" | "b", col: "l" | "m" | "r" }
```

Refresh flag values when the LaunchDarkly SDK reports a change (streaming) or on each render if streaming is not used.

## API response shape (web implementations)

`GET /api/flags?username=...` returns:

```json
{
  "highlightEnabled": true,
  "contextHighlight": true,
  "showMoveCount": false,
  "highlightColor": "green",
  "cohortLabel": "(human-beta-green)",
  "osEmoji": "🍎"
}
```

## Acceptance criteria

An implementation in **10-flag-enablement** is correct when it satisfies all [00-reference acceptance criteria](../00-reference/application.md#acceptance-criteria) **and**:

### Flag 1 — selection highlight

1. With the highlight flag **off**, selected cell styling matches 00-reference (`X` only, no colors)
2. With the highlight flag **on** and context flag **off**, selected cell and username use **pink**
3. Unselected cells are never highlighted regardless of flag state
4. Toggling the flag updates styling without requiring a navigation move

### Flag 2 — context colors

5. With context flag **on** and highlight **on**, login name `human` shows yellow highlight and `Name: human (human-yellow)` in yellow
6. Login name `robot` shows red highlight and `(robot-red)` in red
7. Login name `99human88betazoid` shows green highlight and `(human-beta-green)` in green
8. human+beta → green; robot+beta → purple; beta alone → blue
9. With context flag **off** and highlight **on**, label is `(pink)`; color is pink
10. With highlight **off**, label is `(no-color)`; no username coloring or cell highlight

### Flag 3 — navigation count

11. With the show flag **off**, the header has no Count field
12. With the show flag **on**, the header displays `Count: N` where `N` starts at `0`
13. Each successful navigation move increments `N` by `1`
14. Boundary keypresses that do not change position do not increment `N`

### Visual design

15. Web and console use a dark background suitable for yellow and purple text
16. Username, cohort label, and selection highlight share the same resolved color

### Defaults and offline behavior

17. All four flags default to **off** when targeting is off in LaunchDarkly
18. When the SDK is unavailable, all flags evaluate to their **off** defaults

### Flag 4 — host OS emoji

19. With the show flag **off**, no emoji appears before the username
20. With the show flag **on**, the correct emoji appears for the detected host OS
21. `hostOs` is attached to the evaluation context as a **private attribute**

### Provisioning alignment

22. Flag keys in code match the keys in [terraform/main.tf](terraform/main.tf) and [rest/](rest/) exactly:

```text
configure-grid-selection-green-highlight
configure-grid-selection-context-highlight
show-navigation-move-count
show-host-os-emoji
```

## Further reading

- [README.md](README.md) — example overview and provisioning links
- [00-reference/application.md](../00-reference/application.md) — baseline grid navigator behavior
- [Flag conventions](https://launchdarkly.com/docs/guides/flags/flag-conventions) — naming and tagging guidance
- [project.md](../project.md) — repository conventions and environment variables
