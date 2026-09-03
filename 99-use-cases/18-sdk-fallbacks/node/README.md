# Node web — 18-sdk-fallbacks

Node twin of the Python SDK-fallback lab. A loopback HTTP proxy gates the real
LaunchDarkly stream while every refresh still calls `variationDetail()`.

LaunchDarkly surfaces: **string variation**, **detailed evaluation reason**,
**bounded initialization**, and **streaming updates**.

- https://launchdarkly.com/docs/sdk/features/evaluating
- https://launchdarkly.com/docs/sdk/server-side/node-js

## Run

Provision [`../rest/`](../rest/) first, then:

```bash
npm install
export LD_SDK_KEY="sdk-..."
npm start
```

Open http://127.0.0.1:8181/. Use **Connect stream → Drop stream → Block
initialization** to observe `STREAM → LAST_KNOWN → DEFAULT`.

Optional environment variables:

- `PORT` — web port, default `8181`
- `LD_STREAM_GATE_PORT` — loopback gate, default `8182`
- `LD_START_WAIT` — bounded initialization wait in seconds, default `2`
- `LD_STREAM_ORIGIN` — private LaunchDarkly streaming origin
- `LD_POLL_ORIGIN` — matching polling origin for private deployments

The page is shared with the Python implementation; `/api/config` supplies the
runtime label.
