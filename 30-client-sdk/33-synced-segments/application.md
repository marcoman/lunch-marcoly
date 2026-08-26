# Synced segments application specification

This document defines **33-synced-segments**. Baseline grid behavior is
[02-reference-client-code/application.md](../../02-reference-client-code/application.md).
Client SDK initialize / `variation` / `change:` is
[31-client-evaluation](../31-client-evaluation/application.md).
`identify()` without reload is [32-client-identify](../32-client-identify/application.md).

This example adds a **boolean flag targeted by a big / synced-style segment**.
The page shows an **inner-circle badge** when the current context is in the
segment. Lab Controls **add or remove** the current context key via the REST
API — a stand-in for **Twilio Segment Audiences** in production.

## Overview

| Resource | Key | Role |
|----------|-----|------|
| Flag | `show-inner-circle-badge` | Boolean; **true** when the context is in the segment |
| Segment | `marcoly-inner-circle` | Big/synced-style membership (`unbounded` when the plan allows) |

The flag is **client-side available**. Fallthrough and off are `false`.
A targeting rule: **if context is in `marcoly-inner-circle`, serve `true`**.

## Production vs this lab

| Production | This example |
|------------|----------------|
| Membership from **Twilio Segment Audiences** → LaunchDarkly Audiences destination | REST **add/remove included targets** from the Node host |
| True **synced segment** (external store) | Prefer `unbounded: true` (big/synced). If the project cannot create that, fall back to a **list-based** segment with included keys — same flag rule, same demo |
| Server-side SDKs need a Big Segment store (Redis / DynamoDB / Relay) | **Not used.** Client-side evaluation does not need Redis |

Keywords: **synced segments** · **big segments** · **unbounded** · **segment targeting** ·
**client-side ID** · **identify**

Docs: [Segments](https://launchdarkly.com/docs/home/flags/segments) ·
[Synced segments](https://launchdarkly.com/docs/home/flags/synced-segments) ·
[Update big segment targets](https://launchdarkly.com/docs/api/segments/update-big-segment-targets) ·
[JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript) ·
[React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web)

## Flag: Show inner circle badge

| Attribute | Value |
|-----------|-------|
| **Name** | `Show: inner circle badge` |
| **Key** | `show-inner-circle-badge` |
| **Variation type** | boolean |
| **Tags** | `grid-navigator`, `client-sdk`, `segments`, `synced-segments`, `show` |
| **Client-side** | `usingEnvironmentId: true` |
| **Off / fallthrough** | `false` |
| **Rule** | `segmentMatch` `marcoly-inner-circle` → `true` |

When `true`, the header shows an **inner circle** badge next to the username.
When `false`, no badge (matches 02 aside from dark theme).

## Segment: marcoly-inner-circle

| Attribute | Value |
|-----------|-------|
| **Name** | `Marcoly inner circle` |
| **Key** | `marcoly-inner-circle` |
| **Kind** | Big/synced if `unbounded` is allowed; otherwise list-based included keys |
| **Context kind** | `user` |

A true synced segment is populated **only** via sync or API — not by clicking
members in the dashboard. This lab uses the API for that reason.

## SDK surfaces

| Surface | Role |
|---------|------|
| `initialize` | First login |
| `identify` | Switch context key without reload (reuse 32) |
| `variation` | Read `show-inner-circle-badge` |
| `change:` | Badge updates when membership or the flag changes |

The lab **SDK calls** log records `initialize`, `identify`, `change:`, and `close`.
Do not log `variation` on every WASD move.

## Lab Controls

The page must not hold `LD_API_ACCESS_TOKEN`. The Node host proxies:

- Flag on/off (leave **on** for the demo)
- **Add** / **Remove** the current context key on `marcoly-inner-circle`

## Acceptance criteria

1. Login `initialize`s; Identify switches key without a second `initialize`
2. Badge hidden when the flag is off or the key is not in the segment
3. Add current key → badge appears via `change:` (or after a short refresh) without reload
4. Remove current key → badge disappears
5. Identify to a key not in the segment → badge off; identify back to a member → badge on
6. `/api/config` never includes a server SDK key or API token
7. REST/Terraform create the flag with client-side availability and a segment rule

## Further reading

- [32-client-identify/application.md](../32-client-identify/application.md)
- [31-client-evaluation/application.md](../31-client-evaluation/application.md)
