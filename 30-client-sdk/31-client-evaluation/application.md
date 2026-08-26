# Client evaluation application specification

This document defines the feature flags and desired effects for **31-client-evaluation**.

Baseline grid behavior (login, 3×3, arrows/WASD, `L`/`Q`, **X** only) is
[02-reference-client-code/application.md](../../02-reference-client-code/application.md).
This example adds LaunchDarkly **in the browser**.

## Overview

| Flag key | Type | Purpose |
|----------|------|---------|
| `enable-client-grid-highlight` | string | Colored highlight on the selected cell (`none` when off) |
| `show-client-move-count` | boolean | Show `Count: N` in the header |

Both flags must be **available to client-side SDKs** (`usingEnvironmentId`).
Otherwise `variation` in the browser always returns the code default.

Flags are provisioned in [terraform/](terraform/) and [rest/](rest/).

This is the client analog of [11-flag-enablement](../../10-code-control/11-flag-enablement/application.md)
**without** username cohort override and **without** host OS / `/proc` attributes.

## Relationship to 02

| Aspect | 02-reference-client-code | 31-client-evaluation |
|--------|--------------------------|----------------------|
| LaunchDarkly | None | JavaScript SDK in the page |
| Credential | None | `LD_CLIENT_SIDE_ID` (injected by the local host) |
| Selection | `X` only | `X`; color when highlight flag is on |
| Header | Name, current, previous | Same, plus optional Count |
| Background | Light | Dark (contrast for highlight colors) |

When a flag is **off**, that aspect matches 02 (aside from the dark theme).

## SDK surfaces to notice

| Surface | Role |
|---------|------|
| `initialize` | Connect with the **client-side ID** and a user context (`key` = username) |
| `variation` | Read each flag after init and after `change:` |
| `change:` / `change` | Re-render when targeting changes — no page reload |

The lab **SDK calls** log (and the browser console, prefix `[31 evaluation]`)
records `initialize`, streaming `change:`, and `close`. It does **not** log
`variation` on every navigation keypress. Counters survive logout; a second
login shows `initialize ×2`.

JavaScript SDK: [client-side JavaScript](https://launchdarkly.com/docs/sdk/client-side/javascript).
React Web SDK: [React Web](https://launchdarkly.com/docs/sdk/client-side/react/react-web)
(`useStringVariation`, `useBoolVariation` — same flag keys).
Vue SDK: [Vue](https://launchdarkly.com/docs/sdk/client-side/vue)
(`ldInit`, `useLDFlag` — same flag keys).
Boolean flags: [boolean flags](https://launchdarkly.com/docs/home/flags/boolean).
Client-side availability: [client-side and mobile flags](https://launchdarkly.com/docs/home/flags/creating-flags#make-flags-available-to-client-side-and-mobile-sdks).

## Flag 1: Enable client grid highlight

| Attribute | Value |
|-----------|-------|
| **Name** | `Enable: client grid highlight` |
| **Key** | `enable-client-grid-highlight` |
| **Kind** | Enable |
| **Variation type** | string |
| **Temporary** | No |
| **Tags** | `grid-navigator`, `client-sdk`, `enable`, `ui`, `string` |
| **Off / SDK default** | `none` |
| **Client-side** | `usingEnvironmentId: true` |

| Value | Behavior |
|-------|----------|
| `none` | Selected cell is `X` only — no highlight color |
| `green` / `yellow` / `red` / `blue` / `purple` | Selected cell and username use that color |

Evaluate on grid render and on `change:enable-client-grid-highlight`.

## Flag 2: Show client move count

| Attribute | Value |
|-----------|-------|
| **Name** | `Show: client move count` |
| **Key** | `show-client-move-count` |
| **Kind** | Show (temporary) |
| **Variation type** | boolean |
| **Temporary** | Yes |
| **Tags** | `grid-navigator`, `client-sdk`, `show`, `header` |
| **Off / SDK default** | `false` |
| **Client-side** | `usingEnvironmentId: true` |

| Value | Behavior |
|-------|----------|
| `true` | Header shows `Count: N` (successful moves only) |
| `false` | Count row hidden |

The number is **app state**. The flag only controls visibility.

## Context

```text
{ kind: "user", key: "<username>" }
```

No extra attributes in 31 (`identify` and extra attrs come later).

## Lab Controls

The page must not hold `LD_API_ACCESS_TOKEN` or `LD_SDK_KEY`.
A local Node process may proxy REST `turnFlagOn` / `turnFlagOff` /
`updateFallthroughVariationOrRollout` using those variables from **its** environment.

## Acceptance criteria

1. Empty username is rejected; grid starts at `m/m` with previous `—`
2. Navigation matches 02 (no wrap)
3. Missing `LD_CLIENT_SIDE_ID` or failed init: highlight `none`, count hidden
4. With a valid client-side ID and provisioned flags, `variation` matches the dashboard for that user
5. Toggling a flag (UI or Controls) updates the grid via `change:` without reload; the SDK call log records that `change:` (not WASD `variation`)
6. Highlight off → `X` only; on → fallthrough color
7. Count flag off → no Count row; on → Count increments on successful moves
8. Page source and `/api/config` never include a server SDK key or API token
9. Flags have client-side SDK availability; otherwise document that evaluations stay at defaults
10. Logout then login again increments `initialize` in the SDK call log (count is kept)

## Further reading

- [02-reference-client-code/application.md](../../02-reference-client-code/application.md)
- [SDK credentials](https://launchdarkly.com/docs/home/account/environment/keys)
- [JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript)
- [React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web)
- [Vue SDK](https://launchdarkly.com/docs/sdk/client-side/vue)
