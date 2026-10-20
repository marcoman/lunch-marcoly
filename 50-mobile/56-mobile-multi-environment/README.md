# 56-mobile-multi-environment

**Status: stub — not implemented yet.**

Two LaunchDarkly **environments**, two **mobile keys**, one app. The navigator
shows which environment served the flag. Switching environments uses the other
key and the other flag data.

Read this after [55-automatic-environment-attributes](../55-automatic-environment-attributes/).

Keywords: **multiple environments** · **mobile key** · **mobile SDK**

Docs: [Multiple environments](https://launchdarkly.com/docs/sdk/features/multiple-environments)

## Intended aha

Test and production are different SDK clients, not a string in the context.
The screen names the active environment and the variation it returned.
Flipping the control rebuilds the client with the other mobile key.

## Direction

- Android and iOS.
- The app holds two mobile keys. Neither key is the browser client-side ID.
- One flag key can exist in both environments with different targeting, so the
  switch is visible on the grid.
- No HTTP portal.

## When implementing

1. `application.md`. Do not reuse a single `LD_MOBILE_KEY` for both sides.
2. The drawer shows environment name, key suffix (not the full secret), and
   the variation.
3. Android first, then the same control on iOS.

## Implementation

| Platform | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
