# .NET web — 18-sdk-fallbacks

.NET twin of the Python SDK-fallback lab. Kestrel listens on the web and
loopback-gate ports; the gate proxies and cancels the real LaunchDarkly stream.

LaunchDarkly surfaces: **string variation**, **detailed evaluation reason**,
**bounded initialization**, **service endpoints**, and **streaming updates**.

- https://launchdarkly.com/docs/sdk/features/evaluating
- https://launchdarkly.com/docs/sdk/server-side/dotnet

## Build and run

Provision [`../rest/`](../rest/) first, then:

```bash
dotnet build
export LD_SDK_KEY="sdk-..."
dotnet run
```

Open http://127.0.0.1:8181/. Use **Connect stream → Drop stream → Block
initialization** to observe `STREAM → LAST_KNOWN → DEFAULT`.

Optional variables: `PORT`, `LD_STREAM_GATE_PORT`, `LD_START_WAIT`,
`LD_STREAM_ORIGIN`, and `LD_POLL_ORIGIN`. The web and gate ports default to
`8181` and `8182`.

The project links the shared page from `../python/index.html` into its output.
