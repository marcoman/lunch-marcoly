# 42-local-if-no-sdk

**Status: stub — not implemented yet.**

**DO NOT SHIP.** This example will demonstrate a dashboard flag that exists
(or “should exist”) while the app never calls the SDK — a local `if` /
hardcoded boolean instead of `variation()`. Changing the flag in LaunchDarkly
does nothing.

Parent series: [40-dont-do-this](../README.md). Correct pattern:
[11-flag-enablement](../../10-code-control/11-flag-enablement/) (evaluate the
flag; the variation is the source of truth).

Keywords: **feature flags** · **boolean variation** · **server SDK** ·
**evaluation**

Docs: [Evaluating flags](https://launchdarkly.com/docs/sdk/features/evaluating)

## Intended aha

The rail shows `variation() calls: 0`. The grid follows `if username == "alice"`
(or a constant). The operator flips the flag in LaunchDarkly; the UI does not
move. 11 next to it *does* move.

The SDK may still init so the contrast is honest — we are skipping
**evaluation**, not skipping the whole SDK.

## Do not

- Leave this as the only copy-pasteable grid in the repo with no “do this
  instead” block
- Mix this with [41-no-sdk-singleton](../41-no-sdk-singleton/) (that lab still
  calls `variation()`; it just constructs too many clients)
- Confuse this with [18-sdk-fallbacks](../../99-use-cases/18-sdk-fallbacks/)
  (that lab *does* call `variation()` when LaunchDarkly is gone)

## When implementing

1. `application.md` with dedicated keys so 11 stays independent.
2. Python web first; rail always shows `variation()` count **0** vs the local
   branch that actually drives highlight/count.
3. Side-by-side “do this instead”: one `boolVariation` (or equivalent) per
   decision, same as 11.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
