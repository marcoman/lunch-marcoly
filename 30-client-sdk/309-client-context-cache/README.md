# 309-client-context-cache

**Status: stub — not implemented yet.**

The browser SDK's **local storage** cache of flag values for a context. The
UI calls the cache out: what was stored, for which context, and what the next
load paints before the stream refreshes.

This is not [305-client-bootstrap](../305-client-bootstrap/). Bootstrap is a
payload the page supplies at init. This lesson is the SDK writing and reading
its own cache.

Keywords: **local storage** · **persistent storage** · **client-side SDK** ·
**contexts**

Docs: [Persistent storage](https://launchdarkly.com/docs/sdk/features/storing-data)

## Intended aha

Reload the page and the last flag values appear before the client is ready,
because they were cached for this context. Switch context and the cache key
changes. Clear local storage and the first paint falls back to the default.
The screen points at the cache entry so the runner can see it.

## Direction

- JavaScript, React, and Vue.
- Name local storage in the UI. Do not treat it as an invisible SDK detail.
- Not in the series portal until the app exists. Intended ports **:8390**
  JavaScript · **:8391** React · **:8392** Vue.

## When implementing

1. `application.md`. Keep 305's bootstrap payload out of this lab.
2. JavaScript first. Show the storage key and a short preview of the cached
   values.
3. One button clears the cache so the next load is obvious.

## Implementation

| Client | Directory | Status |
|--------|-----------|--------|
| *(none yet)* | — | Stub |
