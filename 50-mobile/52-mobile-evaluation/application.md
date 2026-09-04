# Mobile evaluation application specification

This document defines the feature flags and desired effects for
**52-mobile-evaluation**.

Baseline grid behavior (login, 2×2 orthogonal tap, logout, lab drawer) is
[51-reference/application.md](../51-reference/application.md). This example
adds LaunchDarkly **on the device**.

It is **not** a port of [31-client-evaluation](../../30-client-sdk/31-client-evaluation/application.md).
31 is the browser JS SDK and a **client-side ID**. 52 is the Android / iOS
**mobile SDK** and a **mobile key**. Flag keys are dedicated — do not reuse
31’s `enable-client-grid-highlight` / `show-client-move-count`.

## Overview

| Flag key | Type | Purpose |
|----------|------|---------|
| `enable-mobile-grid-highlight` | string | Colored highlight on the selected cell (`none` when off) |
| `show-mobile-move-count` | boolean | Show `Count: N` in the header |

Both flags must be **available to mobile SDKs** (`usingMobileKey: true`).
Otherwise `variation` on the device always returns the code default.

Flags are provisioned in [terraform/](terraform/) and [rest/](rest/).

There is **no in-app Controls proxy**. The app must not hold
`LD_API_ACCESS_TOKEN` or `LD_SDK_KEY`. Toggle flags in the LaunchDarkly UI
(or `rest/update-flag.sh`) and watch listeners update the grid.

## Relationship to 51

| Aspect | 51-reference | 52-mobile-evaluation |
|--------|--------------|----------------------|
| LaunchDarkly | None | Android / iOS mobile SDK |
| Credential | None | `LD_MOBILE_KEY` |
| Selection | `X` only | `X`; color when highlight flag is on |
| Header | Name, current, previous | Same, plus optional Count |
| Background | Light | Dark (contrast for highlight colors) |
| Drawer | Position, legal moves | Same, plus flag values and SDK call log |

When a flag is **off**, that aspect matches 51 (aside from the dark theme).

## SDK surfaces to notice

| Surface | Role |
|---------|------|
| `init` / `LDClient.start` | Connect with the **mobile key** and a user context (`key` = username) |
| `stringVariation` / `boolVariation` | Read each flag after init and after a listener fires |
| Flag listener / `observe` | Re-render when targeting changes — no app restart |
| `close` | Tear down on logout so the next login can `init` again |

The lab **SDK calls** log (drawer) records `initialize`, streaming `change:`,
and `close`. It does **not** log `variation` on every tap. Counters survive
logout; a second login shows `initialize ×2`.

Android SDK: [client-side Android](https://launchdarkly.com/docs/sdk/client-side/android).
iOS SDK: [client-side iOS](https://launchdarkly.com/docs/sdk/client-side/ios).
Boolean flags: [boolean flags](https://launchdarkly.com/docs/home/flags/boolean).
Mobile availability: [client-side and mobile flags](https://launchdarkly.com/docs/home/flags/creating-flags#make-flags-available-to-client-side-and-mobile-sdks).

## Flag 1: Enable mobile grid highlight

| Attribute | Value |
|-----------|-------|
| **Name** | `Enable: mobile grid highlight` |
| **Key** | `enable-mobile-grid-highlight` |
| **Kind** | Enable |
| **Variation type** | string |
| **Temporary** | No |
| **Tags** | `grid-navigator`, `mobile-sdk`, `enable`, `ui`, `string` |
| **Off / SDK default** | `none` |
| **Mobile** | `usingMobileKey: true` |

| Value | Behavior |
|-------|----------|
| `none` | Selected cell is `X` only — no highlight color |
| `green` / `yellow` / `red` / `blue` / `purple` | Selected cell and username use that color |

Evaluate after init and on the flag listener for this key.

## Flag 2: Show mobile move count

| Attribute | Value |
|-----------|-------|
| **Name** | `Show: mobile move count` |
| **Key** | `show-mobile-move-count` |
| **Kind** | Show (temporary) |
| **Variation type** | boolean |
| **Temporary** | Yes |
| **Tags** | `grid-navigator`, `mobile-sdk`, `show`, `header` |
| **Off / SDK default** | `false` |
| **Mobile** | `usingMobileKey: true` |

| Value | Behavior |
|-------|----------|
| `true` | Header shows `Count: N` (successful taps only) |
| `false` | Count row hidden |

The number is **app state**. The flag only controls visibility.

## Context

```text
{ kind: "user", key: "<username>" }
```

No extra attributes in 52 (`identify` can wait for a later example).

## Lab drawer (52 additions)

| Field | Content |
|-------|---------|
| Highlight | Current `enable-mobile-grid-highlight` value |
| Count flag | Current `show-mobile-move-count` value |
| SDK calls | `initialize ×N`, `change:<flag> ×N`, `close ×N` |
| Key status | Whether a non-empty mobile key was supplied (never print the key) |

## Presentation

- Default color scheme: **dark mode** (contrast for highlight colors)
- Highlight **off:** selected cell is `X` only, same fill as unselected cells
- Highlight **on:** selected cell fill (and username) use the variation color

## Acceptance criteria

1. Empty username is rejected; grid starts at `t/l` with previous `—`
2. Navigation matches 51 (orthogonal tap, no wrap, no quit)
3. Missing `LD_MOBILE_KEY` or failed init: highlight `none`, count hidden
4. With a valid mobile key and provisioned flags, variation matches the
   dashboard for that user
5. Toggling a flag in the dashboard updates the grid via a listener without
   restart; the SDK call log records that `change:` (not tap `variation`)
6. Highlight off → `X` only; on → fallthrough color
7. Count flag off → no Count row; on → Count increments on successful taps
8. The app never contains a server SDK key or API token
9. Flags have **mobile key** availability; otherwise evaluations stay at defaults
10. Logout then login again increments `initialize` in the SDK call log (move
    count is kept)

## Further reading

- [51-reference/application.md](../51-reference/application.md)
- [SDK credentials](https://launchdarkly.com/docs/home/account/environment/keys)
- [Android SDK](https://launchdarkly.com/docs/sdk/client-side/android)
- [iOS SDK](https://launchdarkly.com/docs/sdk/client-side/ios)
