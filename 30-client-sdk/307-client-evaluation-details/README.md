# 307-client-evaluation-details

**Status: stub — not implemented yet.**

In the browser, show `variationDetail()` next to `variation()`. The detail
call returns the value and the **evaluation reason**. The plain call returns
only the value.

This number used to be reserved for client offline mode. That idea stays
rejected (server fallbacks already live in
[18-sdk-fallbacks](../../99-use-cases/18-sdk-fallbacks/)). **307** is this
lesson.

The server-side tour of four reason kinds is
[109-evaluation-reasons](../../10-code-control/109-evaluation-reasons/). This
lesson is the client SDK pair of calls.

Keywords: **client-side SDK** · **variationDetail** · **evaluation reasons** ·
**client-side ID**

Docs: [Evaluation reasons](https://launchdarkly.com/docs/sdk/features/evaluation-reasons) ·
[JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript)

## Intended aha

The grid can paint from `variation()` alone and hide why that value won. The
rail calls `variationDetail()` for the same flag and shows the kind. Same
flag, two methods, one of them explains the result.

## Direction

- JavaScript, React, and Vue, same shape as 301–306.
- One flag is enough. The lesson is the two methods, not a gallery of four
  reason kinds.
- Call the detail result out in the UI. Do not leave it in the console.
- Not in the series portal until the app exists. Intended ports **:8370**
  JavaScript · **:8371** React · **:8372** Vue.

## When implementing

1. `application.md` with a flag key 301 does not use.
2. JavaScript first. React and Vue follow the 301 pattern.
3. The rail shows both return values on every refresh.

## Implementation

| Client | Directory | Status |
|--------|-----------|--------|
| *(none yet)* | — | Stub |
