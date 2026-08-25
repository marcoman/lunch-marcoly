# Client identify application specification

This document defines **32-client-identify**. Baseline grid behavior is
[02-reference-client-code/application.md](../../02-reference-client-code/application.md).
Client SDK initialize / `variation` / `change:` is
[31-client-evaluation](../31-client-evaluation/application.md).

This example adds **`identify()`**: change the evaluation context **without**
reloading the page or calling `initialize` again.

## Overview

| Flag key | Type | Purpose |
|----------|------|---------|
| `enable-identify-grid-highlight` | string | Highlight color from **targeting rules on context `key`** |
| `show-identify-move-count` | boolean | Count visibility from the same `key` rules |

Both flags are **client-side available** and **on** after provisioning, with
rules for demo users `alice` and `bob`. Fallthrough matches 02 (`none` / hidden).

## What 32 adds over 31

| 31 | 32 |
|----|-----|
| New `initialize` on every login | One client; **`identify(newContext)`** on switch |
| Same flags for every username | Different variations per context **key** |
| Logout (`L`) tears down the SDK | Switch keeps grid position and move count |

JavaScript SDK identify: [changing contexts](https://launchdarkly.com/docs/sdk/features/identify).
Targeting rules: [target with rules](https://launchdarkly.com/docs/home/flags/target-rules).

## Demo users (context key)

Keys are case-sensitive. Buttons in the lab insert lowercase names.

| Context key | Highlight | Count |
|-------------|-----------|-------|
| `alice` | `green` | shown |
| `bob` | `blue` | hidden |
| anyone else (fallthrough) | `none` | hidden |

## Flag 1: Enable identify grid highlight

| Attribute | Value |
|-----------|-------|
| **Name** | `Enable: identify grid highlight` |
| **Key** | `enable-identify-grid-highlight` |
| **Variation type** | string (`none` + colors) |
| **Tags** | `grid-navigator`, `client-sdk`, `identify`, `enable`, `ui`, `string` |
| **Client-side** | `usingEnvironmentId: true` |
| **Off** | `none` |
| **Fallthrough (on)** | `none` |
| **Rules** | `key` in `alice` → `green`; `key` in `bob` → `blue` |

## Flag 2: Show identify move count

| Attribute | Value |
|-----------|-------|
| **Name** | `Show: identify move count` |
| **Key** | `show-identify-move-count` |
| **Variation type** | boolean |
| **Tags** | `grid-navigator`, `client-sdk`, `identify`, `show`, `header` |
| **Client-side** | `usingEnvironmentId: true` |
| **Off / fallthrough** | `false` |
| **Rules** | `key` in `alice` → `true`; `key` in `bob` → `false` |

Move count is **app state**. Identify does not reset it. The flag only controls visibility.

## Context

```text
{ kind: "user", key: "<current username>" }
```

After identify, `variation` and the Context pane must reflect the new key.
Grid `m/m` start still applies only on **login**, not on identify.

## Lab Controls

Same as 31: REST proxy on the Node host. Turning these flags **off** hides
targeting (everyone gets off variations). Leave them **on** for the identify demo.

## Acceptance criteria

1. First login still `initialize`s with `{ kind: "user", key: username }`
2. Switch user calls `identify`, not a second `initialize` / page reload
3. Grid position and move count persist across identify
4. `alice` vs `bob` vs other keys match the table above when flags are on
5. `change:` still updates the grid if targeting is edited while identified
6. `L` logs out and closes the client; `Q` quits
7. No server SDK key or API token in the page

## Further reading

- [31-client-evaluation/application.md](../31-client-evaluation/application.md)
- [Identify](https://launchdarkly.com/docs/sdk/features/identify)
- [JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript)
