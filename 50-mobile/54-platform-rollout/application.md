# Platform rollout application specification

This document defines **54-platform-rollout**.

Baseline navigation is [51-reference](../51-reference/application.md). The device
uses the mobile SDK the way [52-mobile-evaluation](../52-mobile-evaluation/application.md)
does. This example is a **staggered release by platform**.

It is not [53-mobile-experiment](../53-mobile-experiment/application.md).
53 randomizes control versus treatment and uses `platform` only to slice
results. 54 turns the new experience on for Android, then later for iOS.
Users are not randomly assigned to an operating system, so the counts are
not experiment lift.

Docs: [Target with rules](https://launchdarkly.com/docs/home/flags/target-with-rules) ·
[Android SDK](https://launchdarkly.com/docs/sdk/client-side/android) ·
[iOS SDK](https://launchdarkly.com/docs/sdk/client-side/ios) ·
[Custom events](https://launchdarkly.com/docs/sdk/features/events)

Keywords: **targeting rules** · **platform** · **mobile SDK** · **track**

## Flag

| Attribute | Value |
|-----------|-------|
| Name | `Enable: mobile platform rollout` |
| Key | `enable-mobile-platform-rollout` |
| Type | boolean |
| `true` | New release: green selection, header says `Release: on` |
| `false` | Previous experience: plain `X`, header says `Release: waiting` |
| SDK fallback | `false` |
| Mobile | `usingMobileKey: true` |

One flag for both platforms. Do not create separate Android and iOS flags.

## Context

Each app sets `platform` on the user context before `init`:

| App | `platform` |
|-----|------------|
| Android | `android` |
| iOS | `ios` |

The context key is the username.

## Two states

The flag is **on**. Fallthrough serves `false`. One rule serves `true` when
`platform` is in the clause values.

| State | Clause values | Android | iOS |
|-------|---------------|---------|-----|
| 1 | `android` | `true` | `false` |
| 2 | `android`, `ios` | `true` | `true` |

`rest/create-flag.sh` creates state 1. `rest/advance-rollout.sh` adds `ios`
to that clause (`addValuesToClause`). `rest/status.sh` prints the clause
values. A later Terraform apply returns the flag to state 1.

## Events

The first successful orthogonal tap in a login calls

```text
track("mobile_platform_rollout_move")
```

A wall tap does not. Logout then login can send the event again. Confirm the
events on [Live events](https://launchdarkly.com/docs/home/releases/live-events)
(Custom). There is no public API that returns them. A live feed is outside
this exercise.

## Acceptance criteria

1. Empty username is rejected; the grid starts at `t/l`
2. With state 1, Android shows `Release: on` and iOS shows `Release: waiting`
3. `./rest/advance-rollout.sh` prints both platforms, and a flag listener updates a running app without restart
4. After the advance, iOS shows `Release: on`
5. The first real move of a login logs one `track`; a second move in that login does not
6. Missing `LD_MOBILE_KEY`: `Release: waiting`, no `track`
7. The apps never contain an API token or a server SDK key
