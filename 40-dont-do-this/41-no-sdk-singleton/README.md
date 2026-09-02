# 41-no-sdk-singleton

**Status: stub — not implemented yet.**

**DO NOT SHIP.** This example will demonstrate creating a new LaunchDarkly
**server SDK client** on every evaluation (or every request) instead of the
**singleton** / process-wide client LaunchDarkly documents.

Parent series: [40-dont-do-this](../README.md). Correct pattern:
[11-flag-enablement](../../10-code-control/11-flag-enablement/) (one client,
init at startup, `variation()` many times, close on shutdown).

Keywords: **singleton** · **LDClient** · **server SDK** · **initialization**

Docs: [Getting started (server-side)](https://launchdarkly.com/docs/sdk/concepts/getting-started)

## Intended aha

`clients constructed this session: N` climbs on every move or every `/api/flags`
poll. Extra streaming connections, extra init waits, flags that look stuck on
the default, duplicate analytics events.

The GoF singleton *class* is optional. The **one `LDClient` per process** (per
SDK key) is not.

## Do not

- Leave this as the only copy-pasteable grid in the repo with no “do this
  instead” block
- Confuse this with [18-sdk-fallbacks](../../99-use-cases/18-sdk-fallbacks/)
  (that lab is a *healthy* client when LaunchDarkly is gone)
- Teach a new client per *thread* here — later child if we need it

## When implementing

1. `application.md` with dedicated keys so 11 stays independent.
2. Python web first; rail always shows construct count vs 1.
3. Side-by-side “do this instead”: init once, reuse, close once.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
