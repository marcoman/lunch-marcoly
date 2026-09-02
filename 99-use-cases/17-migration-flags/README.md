# 17-migration-flags

**Status: stub — not implemented yet.**

LaunchDarkly **migration flags** for a tiny dual-store cutover on the grid
navigator. This folder is a placeholder so we remember the design locked when
planning the 10-series.

Originally proposed as `10-code-control/16-migration-flags`. We parked it here
because it is a **use case** (stages, dual write, shadow reads), not another
core evaluation lesson like 11–15. `99-use-cases` already has
[16-adaptive-triggers](../16-adaptive-triggers/), so this stub is **17**.

Keywords: **migration flags** · **technology migrations** · **dual write** ·
**shadow reads**

Docs: [Migration flags](https://launchdarkly.com/docs/home/flags/migration)

## Why it is not in 10-code-control

| Series | Job |
|--------|-----|
| **10** | How the SDK evaluates (booleans, variations, rules, multi-context, prerequisites) |
| **99** | Product patterns that sit on top of that (experiments, rollouts, **migrations**) |

The grid should still *look* like [00-reference-code](../../00-reference-code/).
The lesson lives in the **lab rail**: current migration stage and which store
served the read.

## Intended aha

Invent two in-memory (or file) backends for **move count** or **last position**:
store A (old) and store B (new). One **migration flag** drives the stage. The
application does **not** invent `if stage == shadow`; it uses the migration
SDK helpers / stage variation LaunchDarkly documents.

Rough stage path (confirm against current docs when implementing):

```text
off → dual write → shadow → live → ramp down → complete
```

| Stage (sketch) | Write | Read |
|----------------|-------|------|
| Off | A | A |
| Dual write | A and B | A |
| Shadow | A and B | A, compare B |
| Live | A and B | B |
| Ramp down / complete | B | B |

The operator should see stage + serving store change **without** the grid
chrome changing. That is the whole demo.

## Do not

- Put this under `10-code-control/` or reuse 11’s highlight/count keys as the
  migration flag
- Encode the stage machine in application `if` trees if the SDK exposes
  migration helpers
- Teach percentage ramps here — that is [14-progressive-rollout](../14-progressive-rollout/)
- Teach scheduled changes — skipped on purpose (maintenance mode)

## When implementing

1. Write `application.md` (flag key, variation type, stages, acceptance
   criteria, dedicated keys so 11/15 stay independent).
2. Python web first, then twins, then consoles if the rail still teaches.
3. REST (and optional Terraform) to create the **migration** flag — not a
   boolean stand-in.
4. Lab rail always visible: stage, read store, write stores, consistency
   errors on shadow.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
