# 109-evaluation-reasons

**Status: stub — not implemented yet.**

Show **why** a flag evaluated. One screen can reach four reason kinds:
`PREREQUISITE_FAILED`, `RULE_MATCH`, `FALLTHROUGH`, and `ERROR`. The value and
the reason sit next to each other.

[105-prerequisite-flags](../105-prerequisite-flags/) already prints
`PREREQUISITE_FAILED` for one parent/child pair. This lesson walks the four
kinds on purpose.

Keywords: **evaluation reasons** · **variation detail** · **feature flags** ·
**prerequisites** · **targeting rules** · **fallthrough**

Docs: [Evaluation reasons](https://launchdarkly.com/docs/sdk/concepts/evaluation-reasons)

## Intended aha

`variationDetail` returns the value and the reason. The page names the kind
and a short explanation, so a default value is obviously a fallthrough, a rule,
a failed prerequisite, or an error.

`ERROR` is the awkward setup. The other three come from normal targeting.
`ERROR` needs a flag the SDK cannot evaluate cleanly (wrong variation type, or
a flag that fails evaluation). Keep that case visible and separate.

## Direction

- Read `variationDetail`, not only `variation`.
- One control per reason, or one flag whose targeting the lab can switch, so
  the runner sees each kind without leaving the page.
- Do not fold this into [108-flag-approvals](../108-flag-approvals/). Approvals
  are a workflow. Reasons are an evaluation result.
- Not in the series portal until the app exists. Intended ports **:8190–:8193**.

## When implementing

1. `application.md` with dedicated keys so 13, 15, and 16 stay independent.
2. Python web first. The rail shows kind, and the prerequisite key or rule
   index when the SDK provides it.
3. Stage `ERROR` on purpose. Do not treat a network blip as the demo.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
