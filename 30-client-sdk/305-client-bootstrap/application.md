# Client bootstrap application specification

This document defines **305-client-bootstrap**.

Baseline grid behavior is
[02-reference-client-code/application.md](../../02-reference-client-code/application.md).
Evaluation shape matches [301-client-evaluation](../301-client-evaluation/application.md),
with one extra SDK option: **bootstrap**.

## Overview

| Flag key | Type | Bootstrap | Code default |
|----------|------|-----------|--------------|
| `enable-client-bootstrap-highlight` | string | `green` | `none` |
| `show-client-bootstrap-move-count` | boolean | `true` | `false` |

Both flags must be **available to client-side SDKs**. Otherwise the stream
never replaces the bootstrap map.

The bootstrap object lives in the page. It is not fetched from LaunchDarkly
before first paint.

## SDK surface to notice

| Surface | Role |
|---------|------|
| `bootstrap` | Map passed to `initialize` / provider options. `variation` returns these values before `ready` |
| `ready` | Live evaluation replaces the bootstrap map |
| `change:` | Later targeting updates, same as 301 |

JavaScript: `LDClient.initialize(id, context, { bootstrap })`.
React Web: the provider `bootstrap` option (merged into the client before the first network response).
Vue: `ldInit({ options: { bootstrap } })`.

Until `ready`, the grid renders the bootstrap map even if a hook would still
return the code default. The lab then keeps that paint for 8 seconds. A
separate line counts down and says this simulates a startup delay. That line
is larger, bold, and highlighted. Each second plays the short tone from
[107-scheduled-changes](../../10-code-control/107-scheduled-changes/); the
higher tone marks 0. The client still initializes immediately, and the log
records `ready` when it finishes. At 0, the grid renders `variation`. Logout
cancels the countdown.

Docs: [Bootstrapping](https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript).

## Paint line

| Moment | Text |
|--------|------|
| Logged out, or no client-side ID | code default (`none` / hidden) |
| Logged in, countdown running | highlighted countdown line, then the bootstrap paint |
| After countdown, live flags match | stream matches |
| After countdown, live flags differ | stream replaced the bootstrap values |

The SDK call log records `bootstrap` before `ready`.

## Acceptance criteria

1. Empty username is rejected; grid starts at `m/m`
2. With a client-side ID, the first paint is green and the count row is visible, and it stays that way through the 8 second countdown
3. A highlighted countdown line shows the delay. The Paint line then names the stream
4. If the live highlight flag is off, login still paints green through the countdown, then drops to `none`
5. Missing `LD_CLIENT_SIDE_ID`: highlight `none`, count hidden, no bootstrap log
6. Page source and `/api/config` never include a server SDK key or API token
7. Logout then login again logs `bootstrap` again

## Further reading

- [301-client-evaluation](../301-client-evaluation/application.md)
- [Bootstrapping](https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript)

## Lab drawer

The header reads **LaunchDarkly · lab**. Underline tabs sit under that header.
The working tab is the live lab. **About** states this idea, the steps, and one
docs link. About does not repeat the context.
