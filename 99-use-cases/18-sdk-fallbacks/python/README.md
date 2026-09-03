# Python web — 18-sdk-fallbacks

Python grid navigator that demonstrates a server-side SDK's **code default**
versus **last-known flag data** after a real stream interruption.

The host runs a loopback stream gate. The SDK connects through that gate using
its supported `stream_uri` configuration; the browser never receives the SDK
key.

LaunchDarkly surfaces: **string variation**, **detailed evaluation reason**,
**bounded initialization**, and **streaming updates**.

- https://launchdarkly.com/docs/sdk/features/evaluating
- https://launchdarkly.com/docs/sdk/server-side/python

## Provision and run

Provision the dedicated flag from [`../rest/`](../rest/), then:

```bash
python -m pip install -r requirements.txt
export LD_SDK_KEY="sdk-..."
python 18-sdk-fallbacks.py
```

Open http://127.0.0.1:8181/. `PORT` overrides the web port;
`LD_STREAM_GATE_PORT` overrides the loopback gate port.

## Demo

1. Log in and confirm **STREAM**, initialized `yes`, and variation `green`.
2. Click **Drop stream**. The active proxied stream is closed and reconnects
   are rejected. The same client remains initialized and serves `green` from
   its in-memory feature store: **LAST_KNOWN**.
3. Change the flag in LaunchDarkly while disconnected. The app does not receive
   the update.
4. Click **Connect stream**. A fresh client initializes and receives the
   current dashboard value.
5. Click **Block initialization**. The gate closes before constructing a fresh
   client. After the bounded wait, `variation_detail()` returns the code
   default `none`: **DEFAULT**.

`LD_START_WAIT` controls the initialization bound and defaults to 2 seconds.
The blocked-init button therefore pauses briefly by design, but never waits
forever.

## Important distinction

The rail's source is lab transport/store state. The SDK evaluation reason is
shown separately because a normal targeting reason does not identify whether
the SDK used newly streamed or previously cached flag data.

The gate disables event sending for this transport-focused lab. It proxies only
the flag stream and never logs the Authorization header.
