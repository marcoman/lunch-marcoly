# Java web — 18-sdk-fallbacks

Java twin of the Python SDK-fallback lab. `HttpServer` hosts the grid and a
loopback streaming proxy; all modes evaluate with `stringVariationDetail`.

LaunchDarkly surfaces: **string variation**, **detailed evaluation reason**,
**bounded initialization**, **service endpoints**, and **streaming updates**.

- https://launchdarkly.com/docs/sdk/features/evaluating
- https://launchdarkly.com/docs/sdk/server-side/java

## Build and run

Provision [`../rest/`](../rest/) first, then:

```bash
./mvnw clean package
export LD_SDK_KEY="sdk-..."
java -jar target/18-sdk-fallbacks.jar
```

Open http://127.0.0.1:8181/. Use **Connect stream → Drop stream → Block
initialization** to observe `STREAM → LAST_KNOWN → DEFAULT`.

Optional variables: `PORT`, `LD_STREAM_GATE_PORT`, `LD_START_WAIT`,
`LD_STREAM_ORIGIN`, and `LD_POLL_ORIGIN`. The web and gate ports default to
`8181` and `8182`.

Maven packages the shared lab page from `../python/index.html` into the jar.
