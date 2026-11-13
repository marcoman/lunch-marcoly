# Prerequisite flags application specification

This document defines **105-prerequisite-flags**.

Baseline login, grid navigation, header positions, session controls, and
`X`-only selection come from
[00-reference-feature/application.md](../../00-reference-feature/application.md).
This example uses **dedicated** flags that **cite**
[101-flag-enablement](../101-flag-enablement/) (same highlight + count idea)
but do **not** share 11's keys. A second child cites
[102-flag-variations](../102-flag-variations/) and does **not** share that key
either. A LaunchDarkly **prerequisite** on each child requires the parent to
be on **and** serving `green` before that child may evaluate.

## Overview

This lab teaches **flag prerequisites**. One parent gates two children. Neither
child is a second `if` in application code. LaunchDarkly decides whether each
child is eligible to evaluate.

It is **not** [101-flag-enablement](../101-flag-enablement/). **11** evaluates
highlight and count independently. **105** makes both the count and the host
emoji depend on highlight. Do not re-teach cohort words, color override, or
anonymous contexts. The emoji is the second dependent so a parent-off hides
two things at once.

Keywords: **prerequisites** · **dependent flag** · **off variation** ·
**feature flags**

Docs: [Flag prerequisites](https://launchdarkly.com/docs/home/flags/prereqs) ·
[Flag hierarchy](https://launchdarkly.com/docs/guides/flags/flag-hierarchy) ·
[Evaluating flags](https://launchdarkly.com/docs/sdk/features/evaluating)

## The aha (the whole lesson)

Both children stay **on** with fallthrough `true`. The operator still only
sees `Count: N` and the host emoji when the shared prerequisite is met.

| Parent (`enable-grid-selection-highlight-prereq`) | Each child | Header |
|--------------------------------------------|-----------------|--------|
| **On**, serving **`green`** | Evaluated → `true` | Green highlight, `Count: N`, **and** the host emoji |
| **Off** (serves `none`) | **Not evaluated** → off variation `false` | `X` only, **no count**, **no emoji** |
| **On**, serving a **non-green** color | **Not evaluated** → off variation `false` | That color highlight, **no count**, **no emoji** |

Same child flags. Same child targeting. LaunchDarkly still hides both the
count and the emoji because the parent is off or is not serving the specified
variation.

Application code must not implement `if highlight then evaluate count` or
`if highlight then show emoji`. Evaluate all three flags with the SDK. Each
child variation (and its evaluation reason) is the source of truth.

## Flags

Do **not** reuse 11's keys. Suffix **`prereq`** names the capability (not the
folder number). Display names and descriptions **cite** 11 so the dashboard
stays greppable.

### Parent — Enable grid selection highlight (prereq)

| Attribute | Value |
|-----------|-------|
| **Kind** | Enable (operational) |
| **Name** | `Enable: grid selection highlight (prereq)` |
| **Key** | `enable-grid-selection-highlight-prereq` |
| **Variation type** | string |
| **Temporary** | No |
| **Tags** | `grid-navigator`, `enable`, `ui`, `string`, `prereq` |
| **Description** | `105-prerequisite-flags parent. Cites 101-flag-enablement flag enable-grid-selection-highlight (same string highlight: none or a color). Dedicated key so 101 stays independent. Children show-navigation-move-count-prereq and show-anonymous-host-os-emoji-prereq require this flag on and serving green.` |
| **Off variation** | `none` |
| **Fallthrough (lab default)** | `green` |
| **SDK default when offline** | `none` |

Same colors as 11: `none`, `green`, `yellow`, `red`, `blue`, `purple`.
Selected cell and username use the served color when it is not `none`.
No cohort override in this example.

### Child — Show navigation move count (prereq)

| Attribute | Value |
|-----------|-------|
| **Kind** | Show (temporary) |
| **Name** | `Show: navigation move count (prereq)` |
| **Key** | `show-navigation-move-count-prereq` |
| **Variation type** | boolean |
| **Temporary** | Yes |
| **Tags** | `grid-navigator`, `show`, `header`, `prerequisite`, `prereq` |
| **Description** | `105-prerequisite-flags dependent. Cites 101-flag-enablement flag show-navigation-move-count (same Count: N visibility). Dedicated key. Prerequisite: enable-grid-selection-highlight-prereq on and serving green.` |
| **Off variation** | `false` |
| **Fallthrough** | `true` |
| **Environment default** | On |
| **SDK default when offline** | `false` |
| **Prerequisite** | Parent **on** and serving **`green`** |

When `true`, the header shows **`Count: N`**. When `false`, omit the count
line entirely. `N` is application state (successful moves this session),
not a flag variation.

### Child — Show anonymous host OS emoji (prereq)

| Attribute | Value |
|-----------|-------|
| **Kind** | Show (temporary) |
| **Name** | `Show: anonymous host OS emoji (prereq)` |
| **Key** | `show-anonymous-host-os-emoji-prereq` |
| **Variation type** | boolean |
| **Temporary** | Yes |
| **Tags** | `grid-navigator`, `show`, `header`, `prerequisite`, `prereq`, `emoji` |
| **Description** | `105-prerequisite-flags second dependent. Cites 102-flag-variations flag show-anonymous-host-os-emoji (host OS emoji before the username). Dedicated key. Same prerequisite as the count child. Evaluated on the user context.` |
| **Off variation** | `false` |
| **Fallthrough** | `true` |
| **Environment default** | On |
| **SDK default when offline** | `false` |
| **Prerequisite** | Parent **on** and serving **`green`** |

When `true`, the header shows the host emoji before the username
(🍎 macOS, 🐧 Linux, 🪟 Windows, 😊 anything else). When `false`, omit the
emoji. The OS is detected on the server for display. It is not a context
attribute in this lab, and the context is the logged-in user, not 102's
anonymous context.

### Prerequisite relationship

Provisioned on the **child**, per environment:

| Dependent | Prerequisite flag | Required variation |
|-----------|-------------------|--------------------|
| `show-navigation-move-count-prereq` | `enable-grid-selection-highlight-prereq` | `green` |
| `show-anonymous-host-os-emoji-prereq` | `enable-grid-selection-highlight-prereq` | `green` |

LaunchDarkly treats a prerequisite as unmet if the parent is **off**, even
if off would serve `none` and `none` is not the required variation anyway.
Unmet prerequisite → that child serves its **off variation** (`false`).
Evaluation reason kind is `PREREQUISITE_FAILED` with `prerequisiteKey` =
`enable-grid-selection-highlight-prereq`. Both children fail together when
the parent is off or is not serving `green`.

Do not chain the children. Do not make the parent depend on a child. Do not
add a third prerequisite.

## Relationship to 11

**11** keeps `enable-grid-selection-highlight` and `show-navigation-move-count`
independent. **15** never patches those keys. Same project/environment is
fine.

## Login and context

Login is a **username** only (trimmed, lowercased for the context key). No
org picker, no team picker, no Alice/Bob radio cards. This example is not
about targeting rules or multi-contexts.

Every evaluation uses a single `user` context:

```json
{
  "kind": "user",
  "key": "alice"
}
```

Evaluate **all three** flags against that same context on each render (and when
Controls change targeting). Re-render without requiring a navigation move.

## Header behavior

```text
Name: 🍎 alice              ← emoji only when the emoji child evaluates true
Current position: m/m       ← name color follows the parent
Previous position: —
Count: 0                    ← only when the count child evaluates true
```

When the prerequisite fails, drop the Count line and the emoji. Keep Name /
Current / Previous. Highlight follows the parent string, independently of
either child.

## LaunchDarkly lab

The right drawer has **Prerequisite** and **About**. Prerequisite keeps the dependency visible while Controls change:

- **Controls** — parent on/off and parent fallthrough color; each child on/off
  (leave **both children on** for the demo). Do **not** edit either
  prerequisite from the lab UI.
- **Context window (always visible)** — user key
- **Current result (always visible)** — parent variation, both child
  variations, whether the prerequisite was met, and all three evaluation
  reasons
- **Live dependency** — parent on top, count and emoji forked underneath
- **Events / status rail (always visible)** — control actions, SDK
  variations, `PREREQUISITE_FAILED` vs normal targeting
- **About** — parent → child table, prerequisite keywords, docs links above

Demo path: both children on, parent on/`green` (count and emoji visible) →
turn **parent off** (both disappear, both reasons `PREREQUISITE_FAILED`) →
parent on again, optionally switch fallthrough to **yellow** (highlight
changes, count and emoji still hidden).

## API

`GET /api/flags?username=alice`

```json
{
  "username": "alice",
  "highlightColor": "green",
  "showMoveCount": true,
  "showHostEmoji": true,
  "hostOs": "macos",
  "hostEmoji": "🍎",
  "prerequisiteMet": true,
  "ldContext": { "kind": "user", "key": "alice" },
  "parent": {
    "key": "enable-grid-selection-highlight-prereq",
    "value": "green",
    "reason": { "kind": "FALLTHROUGH" }
  },
  "child": {
    "key": "show-navigation-move-count-prereq",
    "value": true,
    "reason": { "kind": "FALLTHROUGH" }
  },
  "emoji": {
    "key": "show-anonymous-host-os-emoji-prereq",
    "value": true,
    "reason": { "kind": "FALLTHROUGH" }
  }
}
```

Parent off example: `"highlightColor": "none"`, `"showMoveCount": false`,
`"showHostEmoji": false`, `"hostEmoji": ""`, `"prerequisiteMet": false`,
both child reasons `"kind": "PREREQUISITE_FAILED"`.

`GET /api/bootstrap` returns the banner and control configuration.
`GET` and `POST /api/flag-controls` expose parent on/off, parent fallthrough
color, and each child on/off. They must **not** add, change, or remove either
prerequisite.

## Acceptance criteria

1. Login is username only; context is a single `user` kind
2. Application evaluates all three flag keys with the SDK; it does not gate
   either child evaluation with application `if` logic
3. Parent off → selected cell is `X` only, Count is hidden, and the emoji is hidden
4. Parent on serving `green` and both children on → green highlight, `Count: N`,
   and the host emoji
5. Parent on serving a non-green color → that highlight, Count hidden, emoji hidden
6. Count child off → Count hidden even when the prerequisite is met; the emoji
   can still show
7. Unmet prerequisite produces each child's off variation `false` and reason
   `PREREQUISITE_FAILED` (not application-invented hide logic)
8. Controls change parent on/off, parent fallthrough color, and each child
   on/off only — never either prerequisite relationship
9. Live context, current result, and events/status remain visible together
   while Controls change. The dependency diagram shows one parent forked to
   two children
10. REST creates the three **`-prereq`** flags (not 11's or 102's keys),
    sets both children's prerequisite to parent/`green`, turns each child on,
    fallthrough `true`

## Further reading

- [101-flag-enablement/application.md](../101-flag-enablement/application.md)
- [00-reference-feature/application.md](../../00-reference-feature/application.md)
- [104-multi-context-targeting/application.md](../104-multi-context-targeting/application.md)
