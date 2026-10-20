# Prerequisite flags application specification

This document defines **15-prerequisite-flags**.

Baseline login, grid navigation, header positions, session controls, and
`X`-only selection come from
[00-reference-code/application.md](../../00-reference-code/application.md).
This example uses **dedicated** flags that **cite**
[11-flag-enablement](../11-flag-enablement/) (same highlight + count idea)
but do **not** share 11's keys. A LaunchDarkly **prerequisite** requires the
parent to be on **and** serving `green` before the child may evaluate.

## Overview

This lab teaches **flag prerequisites**. The dependent flag is not a second
`if` in application code. LaunchDarkly decides whether the child is eligible
to evaluate at all.

It is **not** [11-flag-enablement](../11-flag-enablement/). **11** evaluates
highlight and count independently. **15** makes count depend on highlight.
Do not re-teach cohort words, color override, or host-OS emoji.

Keywords: **prerequisites** · **dependent flag** · **off variation** ·
**feature flags**

Docs: [Flag prerequisites](https://launchdarkly.com/docs/home/flags/prereqs) ·
[Flag hierarchy](https://launchdarkly.com/docs/guides/flags/flag-hierarchy) ·
[Evaluating flags](https://launchdarkly.com/docs/sdk/features/evaluating)

## The aha (the whole lesson)

`show-navigation-move-count-prereq` stays **on** with fallthrough `true`. The
operator still only sees `Count: N` when the prerequisite is met.

| Parent (`enable-grid-selection-highlight-prereq`) | Child targeting | Header |
|--------------------------------------------|-----------------|--------|
| **On**, serving **`green`** | Evaluated → `true` | Green highlight **and** `Count: N` |
| **Off** (serves `none`) | **Not evaluated** → off variation `false` | `X` only, **no count** |
| **On**, serving a **non-green** color | **Not evaluated** → off variation `false` | That color highlight, **no count** |

Same child flag. Same child targeting. LaunchDarkly still hides the count
because the parent is off or is not serving the specified variation.

Application code must not implement `if highlight then evaluate count`.
Evaluate both flags with the SDK. The child variation (and its evaluation
reason) is the source of truth.

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
| **Description** | `15-prerequisite-flags parent. Cites 11-flag-enablement flag enable-grid-selection-highlight (same string highlight: none or a color). Dedicated key so 11 stays independent. Child show-navigation-move-count-prereq requires this flag on and serving green.` |
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
| **Description** | `15-prerequisite-flags dependent. Cites 11-flag-enablement flag show-navigation-move-count (same Count: N visibility). Dedicated key. Prerequisite: enable-grid-selection-highlight-prereq on and serving green.` |
| **Off variation** | `false` |
| **Fallthrough** | `true` |
| **Environment default** | On |
| **SDK default when offline** | `false` |
| **Prerequisite** | Parent **on** and serving **`green`** |

When `true`, the header shows **`Count: N`**. When `false`, omit the count
line entirely. `N` is application state (successful moves this session),
not a flag variation.

### Prerequisite relationship

Provisioned on the **child**, per environment:

| Dependent | Prerequisite flag | Required variation |
|-----------|-------------------|--------------------|
| `show-navigation-move-count-prereq` | `enable-grid-selection-highlight-prereq` | `green` |

LaunchDarkly treats the prerequisite as unmet if the parent is **off**, even
if off would serve `none` and `none` is not the required variation anyway.
Unmet prerequisite → child serves its **off variation** (`false`). Evaluation
reason kind is `PREREQUISITE_FAILED` with `prerequisiteKey` =
`enable-grid-selection-highlight-prereq`.

Do not add a second prerequisite. Do not make the parent depend on the child.

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

Evaluate **both** flags against that same context on each render (and when
Controls change targeting). Re-render without requiring a navigation move.

## Header behavior

```text
Name: alice                 ← green when parent serves green
Current position: m/m
Previous position: —
Count: 0                    ← only when the child evaluates true
```

When the prerequisite fails, drop the Count line. Keep Name / Current /
Previous. Highlight follows the parent string, independently of the child.

## LaunchDarkly lab

The permanent shell keeps the dependency visible while Controls change:

- **Controls** — parent on/off and parent fallthrough color; child on/off
  (leave the **child on** for the demo). Do **not** edit the prerequisite
  from the lab UI.
- **Context window (always visible)** — user key
- **Current result (always visible)** — parent variation, child variation,
  whether the prerequisite was met, and both evaluation reasons
- **Events / status rail (always visible)** — control actions, SDK
  variations, `PREREQUISITE_FAILED` vs normal targeting
- **About** — parent → child table, prerequisite keywords, docs links above

Demo path: child on, parent on/`green` (count visible) → turn **parent off**
(count disappears, reason `PREREQUISITE_FAILED`) → parent on again, optionally
switch fallthrough to **yellow** (highlight changes, count still hidden).

## API

`GET /api/flags?username=alice`

```json
{
  "username": "alice",
  "highlightColor": "green",
  "showMoveCount": true,
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
  }
}
```

Parent off example: `"highlightColor": "none"`, `"showMoveCount": false`,
`"prerequisiteMet": false`, child reason `"kind": "PREREQUISITE_FAILED"`.

`GET /api/bootstrap` returns the banner and control configuration.
`GET` and `POST /api/flag-controls` expose parent on/off, parent fallthrough
color, and child on/off. They must **not** add, change, or remove the
prerequisite.

## Acceptance criteria

1. Login is username only; context is a single `user` kind
2. Application evaluates both flag keys with the SDK; it does not gate the
   child evaluation with application `if` logic
3. Parent off → selected cell is `X` only and Count is hidden
4. Parent on serving `green` and child on → green highlight and `Count: N`
5. Parent on serving a non-green color → that highlight and Count hidden
6. Child off → Count hidden even when the prerequisite is met
7. Unmet prerequisite produces child off variation `false` and reason
   `PREREQUISITE_FAILED` (not application-invented hide logic)
8. Controls change parent on/off, parent fallthrough color, and child on/off
   only — never the prerequisite relationship
9. Live context, current result, and events/status remain visible together
   while Controls change
10. REST and Terraform create the two **`-prereq`** flags (not 11's keys),
    set the child’s prerequisite to parent/`green`, turn the child on,
    fallthrough `true`

## Further reading

- [11-flag-enablement/application.md](../11-flag-enablement/application.md)
- [00-reference-code/application.md](../../00-reference-code/application.md)
- [14-multi-context-targeting/application.md](../14-multi-context-targeting/application.md)
