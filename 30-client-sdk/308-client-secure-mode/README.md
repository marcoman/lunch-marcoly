# 308-client-secure-mode

**Status: stub — not implemented yet.**

**Secure mode** for the browser SDK. The server computes the hash for the
current context. The page initializes with that hash, so the browser cannot
invent another user's key and evaluate as them.

Keywords: **secure mode** · **client-side SDK** · **context** ·
**client-side ID**

Docs: [Secure mode](https://launchdarkly.com/docs/sdk/features/secure-mode)

## Intended aha

Without the hash, the page's context key is whatever the browser sends. With
secure mode, a mismatched hash fails initialization. The lab should show a
valid hash succeeding and a tampered context failing, and say which one the
server signed.

## Direction

- The hash is computed on the server. The SDK key never goes to the page.
- JavaScript, React, and Vue.
- Not in the series portal until the app exists. Intended ports **:8380**
  JavaScript · **:8381** React · **:8382** Vue.

## When implementing

1. `application.md`. The hash endpoint stays server-side.
2. JavaScript first.
3. The rail shows "hash matches this context" or the secure-mode failure.

## Implementation

| Client | Directory | Status |
|--------|-----------|--------|
| *(none yet)* | — | Stub |
