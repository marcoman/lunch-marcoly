# 02-reference-client-code

Browser-side reference for **lunch-marcoly**: the same 3×3 grid navigator as [00-reference-code](../00-reference-code/), running **in the page**. No LaunchDarkly.

## What this demonstrates

The **application is client JavaScript**. A tiny Node process only serves static files so you can open a URL. Python / Java / .NET static hosts can be added later; they should not own login or movement.

See [application.md](application.md) for behavior and acceptance criteria. Selection is **`X` only** — no highlight colors.

This example is the baseline for [30-client-sdk](../30-client-sdk/) (client-side ID, `variation`, `identify`, synced segments).

## Prerequisites

No LaunchDarkly account. Set up Node once using the [root README](../README.md#building-code) ([nvm](https://github.com/nvm-sh/nvm) + repository [`.nvmrc`](../.nvmrc)).

## Build and run

| Language | Directory | Build | Run | URL |
|----------|-----------|-------|-----|-----|
| JavaScript (browser) | [javascript/](javascript/) | *(none)* | `node 02-reference-client-code.js` | [http://127.0.0.1:8020/](http://127.0.0.1:8020/) |

Open the language README for **Build**, **Run**, and **What to expect**.

## Language implementations

| Language | Directory | Application type | Status |
|----------|-----------|------------------|--------|
| JavaScript | [javascript/](javascript/) | Browser application (static files) | Done |

## Further reading

- [application.md](application.md) — grid behavior (matches 00 in the browser)
- [00-reference-code](../00-reference-code/) — server and console twins
- [project.md](../project.md) — repository conventions
