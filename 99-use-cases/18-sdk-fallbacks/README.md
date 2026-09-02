# 18-sdk-fallbacks

**Status: stub — not implemented yet.**

Simulate losing LaunchDarkly (init never succeeds, or the stream dies after a
good evaluation) and show the grid still working from **SDK fallbacks**.

Keywords: **default variation** · **offline** · **persistent store** ·
**evaluation**

Docs: [Evaluating flags](https://launchdarkly.com/docs/sdk/features/evaluating)

## Why 99, not 10

| Series | Job |
|--------|-----|
| **10** | How a healthy SDK evaluates (booleans, variations, rules, multi-context, prerequisites) |
| **99** | What happens when the control plane is **unavailable** |

The grid should still *look* like [00-reference-code](../../00-reference-code/).
The lesson lives in the **lab rail**: `source: DEFAULT` vs `LAST_KNOWN` vs
`STREAM`. Without that label it just looks broken.

## Intended aha

Two modes, one lab. Do not mix in Relay Proxy for v1.

| Mode | What you simulate | What the SDK should do |
|------|-------------------|-------------------------|
| Never initialized | Bad/blocked SDK key, or init timeout | `variation()` returns the **default you passed** (`none` / `false`) |
| Stream dies after a good eval | Kill streaming after serving `green` | In-memory (and optional file store) **last known** — still `green`, not the default |

Highlight (or count) follows whatever the SDK actually returned. The operator
toggles “block init” vs “drop stream” and watches the source line change.

## Do not

- Teach percentage or progressive rollouts — that is
  [14-progressive-rollout](../14-progressive-rollout/)
- Treat “SDK default” and “last known after a successful init” as the same
  thing
- Hang the process waiting forever for LaunchDarkly
- Invent application `if not connected` branching that skips `variation()`

## When implementing

1. Write `application.md` (dedicated flag key so 11 stays independent, how to
   force each mode, acceptance criteria for the three sources).
2. Python web first; rail always visible.
3. Confirm current SDK knobs (init timeout, offline, persistent store) per
   language before copying Python’s cheat.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
