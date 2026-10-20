# 55-automatic-environment-attributes

**Status: stub — not implemented yet.**

The mobile SDK attaches **automatic environment attributes** (OS, device, and
the rest of that set) without the app putting them on the context. The 2×2
navigator shows the attributes the SDK added.

Keywords: **automatic environment attributes** · **mobile SDK** · **contexts** ·
**mobile key**

Docs: [Automatic environment attributes](https://launchdarkly.com/docs/sdk/features/environment-attributes)

## Intended aha

The app builds a small context (the person). The detail view also lists
attributes the application code never set. Android and iOS do not show the
same device values, and the screen says which ones came from the SDK.

## Direction

- Android and iOS, after [54-platform-rollout](../54-platform-rollout/).
- Do not hand-set `os` or `device` in the app and call that the lesson.
- A flag may target one of those attributes so the grid changes when the
  attribute matches. The point is still the attribute list.
- No HTTP portal. Run on an emulator or simulator.

## When implementing

1. `application.md` with a flag key 52–54 do not use.
2. Show the generated attributes in the drawer on both platforms.
3. Mark each row as app-supplied or SDK-supplied.

## Implementation

| Platform | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
