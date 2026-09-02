# 40-dont-do-this

**Status: stub series — not implemented yet.**

Examples of **misusing** LaunchDarkly. Each child is one anti-pattern, with a
loud **do not ship** banner and a short pointer at the correct pattern (usually
[11-flag-enablement](../10-code-control/11-flag-enablement/)).

This is **not** [99-use-cases](../99-use-cases/) (good product patterns) and
**not** [10-code-control](../10-code-control/) (healthy SDK evaluation).

Keywords: **anti-patterns** · **server SDK** · **do not copy**

## Children

| Example | Folder | Status |
|---------|--------|--------|
| **41** | [41-no-sdk-singleton/](41-no-sdk-singleton/) | Stub — new `LDClient` per evaluation |
| **42** | [42-local-if-no-sdk/](42-local-if-no-sdk/) | Stub — local `if` / hardcoded boolean, no `variation()` |

## Safety

People will copy these. Every implemented example must:

- Open with **DO NOT SHIP**
- Show the cost in the lab rail (client count, skipped `variation()`, …)
- End with a 10-line “do this instead” that matches 11

Do not mix 41 and 42 in one lab.
