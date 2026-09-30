# Client track events application specification

This document defines **36-client-track-events**.

Baseline grid behavior is
[02-reference-client-code/application.md](../../02-reference-client-code/application.md).
Flag evaluation matches [31-client-evaluation](../31-client-evaluation/application.md).
The lesson is client SDK **`track()`**.

## Overview

| Event key | When | Data |
|-----------|------|------|
| `login_completed` | After the client is ready | none |
| `grid_move` | Selected cell changes | `{ from, to }` |

`track` queues the event for the current context. `flush()` sends the batch
now. A move that does not change the cell (a wall) does not call `track`.

Docs: [Sending custom events](https://launchdarkly.com/docs/sdk/features/events).

The lab log is the local proof. In LaunchDarkly, confirm the same events on
[Live events](https://launchdarkly.com/docs/home/releases/live-events) (Custom).
There is no public API that returns them. A live feed is outside this exercise.

## SDK surface to notice

| Surface | Role |
|---------|------|
| `track(key)` | `login_completed` |
| `track(key, data)` | `grid_move` with `{ from, to }` |
| `flush()` | Send the queued batch without waiting for the interval |

JavaScript: `ldClient.track` / `ldClient.flush` after `waitForInitialization`.
React Web: `useLDClient().track` once initialization status is `complete`, and
again when `moveCount` increases.
Vue: `ldClient.track` on `ready`, and from the grid shell when `moveCount` increases.

Missing `LD_CLIENT_SIDE_ID`: the page does not call `track`.

## Flags

| Flag key | Type | Code default |
|----------|------|--------------|
| `enable-client-track-highlight` | string | `none` |
| `show-client-track-move-count` | boolean | `false` |

Both flags must be **available to client-side SDKs**. They are dedicated keys
so 31 stays independent. The events do not depend on either flag being on.

## Acceptance criteria

1. Empty username is rejected; grid starts at `m/m`
2. With a client-side ID, login logs `track login_completed` once the client is ready
3. A successful move logs `track grid_move` with `from` and `to`
4. A wall bump does not log `grid_move`
5. Logout then login logs `login_completed` again
6. Missing `LD_CLIENT_SIDE_ID`: no `track` calls
7. Page source and `/api/config` never include a server SDK key or API token

## Further reading

- [31-client-evaluation](../31-client-evaluation/application.md)
- [Sending custom events](https://launchdarkly.com/docs/sdk/features/events)
- [34-synced-segments-twilio](../34-synced-segments-twilio/) — Segment `track`, a different product
