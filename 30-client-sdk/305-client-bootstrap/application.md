# Client bootstrap application specification

This document defines **35-client-bootstrap**.

Baseline grid behavior is
[02-reference-client-code/application.md](../../02-reference-client-code/application.md).
Evaluation shape matches [31-client-evaluation](../31-client-evaluation/application.md),
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
| `change:` | Later targeting updates, same as 31 |

JavaScript: `LDClient.initialize(id, context, { bootstrap })`.
React Web: the provider `bootstrap` option (merged into the client before the first network response).
Vue: `ldInit({ options: { bootstrap } })`.

Until `ready`, the grid renders the bootstrap map even if a hook would still
return the code default. After `ready`, the grid renders `variation`.

Docs: [Bootstrapping](https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript).

## Paint line

| Moment | Text |
|--------|------|
| Logged out, or no client-side ID | code default (`none` / hidden) |
| Logged in, before ready | bootstrap `highlight=green count=true` |
| After ready, live flags match | stream matches |
| After ready, live flags differ | stream replaced the bootstrap values |

The SDK call log records `bootstrap` before `ready`.

## Acceptance criteria

1. Empty username is rejected; grid starts at `m/m`
2. With a client-side ID, the first paint is green and the count row is visible, before `ready`
3. The Paint line names bootstrap, then stream
4. If the live highlight flag is off, reload still paints green first, then drops to `none` after `ready`
5. Missing `LD_CLIENT_SIDE_ID`: highlight `none`, count hidden, no bootstrap log
6. Page source and `/api/config` never include a server SDK key or API token
7. Logout then login again logs `bootstrap` again

## Further reading

- [31-client-evaluation](../31-client-evaluation/application.md)
- [Bootstrapping](https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript)
