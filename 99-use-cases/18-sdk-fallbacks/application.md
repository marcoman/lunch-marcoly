# SDK Fallbacks Use Case

This document defines **18-sdk-fallbacks** under [99-use-cases](../README.md).

## Goal

Show the two server-side SDK outcomes that are often both called “fallback”:

1. A client that **never initializes** returns the default passed to
   `variation()`.
2. A client that initialized successfully and then loses its stream continues
   evaluating from **last-known flag data**.

The application always calls `variation()`. It does not branch on connection
state.

Keywords: **server SDK** · **default variation** · **streaming** ·
**last-known flag data** · **evaluation**

Docs: [Evaluating flags](https://launchdarkly.com/docs/sdk/features/evaluating) ·
[Server-side SDK initialization](https://launchdarkly.com/docs/sdk/concepts/getting-started)

## Flag

| Attribute | Value |
|-----------|-------|
| Name | `Enable: SDK fallback grid highlight` |
| Key | `enable-sdk-fallback-grid-highlight` |
| Type | String |
| Variations | `none`, `green` |
| Off variation | `none` |
| Provisioned state | On, fallthrough `green` |

The application passes **`none`** as the code default. A healthy stream
therefore resolves `green`; a never-initialized client resolves `none`.

Do not reuse another grid flag. The demo depends on a known live value that is
different from the code default.

## Web stream gate

Each web host starts a loopback reverse proxy and points its SDK's public
streaming service endpoint at it. The gate only controls the streaming data
source; evaluations still go through the SDK. Python uses `stream_uri`; Node
uses `streamUri`; Java and .NET use their service-endpoint builders.

| Mode | Gate | Client | Expected source |
|------|------|--------|-----------------|
| Connect stream | Open | Newly initialized | `STREAM` |
| Drop stream | Closed after initialization | Same client and in-memory store | `LAST_KNOWN` |
| Block initialization | Closed before constructing a new client | Never initialized; bounded wait | `DEFAULT` |

`Drop stream` closes the active proxied response and rejects reconnects. It
must not close or replace the SDK client. `Block initialization` does replace
the client so there is no prior in-memory state to evaluate.

The source label describes the demonstrated data path:

- `STREAM`: the gate has an active upstream stream.
- `LAST_KNOWN`: this client initialized before the gate was closed.
- `DEFAULT`: this client never initialized.

The LaunchDarkly evaluation reason remains visible separately. Evaluation
reasons describe targeting decisions and errors; they do not identify whether
flag data arrived moments ago or came from the SDK's in-memory store.

## Application behavior

1. Login requires a non-empty username and builds a `user` context.
2. The selected cell starts at `m/m`; arrow keys and WASD navigate without
   wrap-around.
3. The host evaluates `enable-sdk-fallback-grid-highlight` with default
   `none` on every poll.
4. `green` colors the selected cell and username; `none` preserves the
   reference application's plain `X`.
5. The rail always shows mode, source, raw variation, evaluation reason,
   initialization state, stream state, and whether this client was ever
   initialized.
6. Controls connect the stream, drop the active stream, or replace the client
   while initialization is blocked.
7. `L` logs out and `Q` closes the web application view.

## Demo sequence

1. Provision the flag and start with a valid `LD_SDK_KEY`.
2. **Connect stream**: wait for `STREAM`, initialized `yes`, variation `green`.
3. **Drop stream**: source becomes `LAST_KNOWN`; variation remains `green`.
4. Change the flag in LaunchDarkly while disconnected. The app remains on its
   last-known value because the update cannot cross the gate.
5. **Connect stream**: the fresh client initializes and serves the current
   dashboard value.
6. **Block initialization**: source becomes `DEFAULT`, initialized `no`,
   variation `none`.

## Acceptance criteria

- [ ] Provisioning creates the dedicated string flag, on with `green`
      fallthrough and `none` off variation.
- [ ] Startup and every mode transition use a bounded initialization wait.
- [ ] The application calls `variation_detail()` in all three modes with code
      default `none`.
- [ ] Dropping the stream keeps the same SDK client and returns its last-known
      value.
- [ ] Blocking initialization constructs a fresh client with no prior flag
      data and returns `none`.
- [ ] The rail distinguishes source from LaunchDarkly evaluation reason.
- [ ] No SDK key is sent to the browser or written to logs.
- [ ] Shutdown closes the SDK client, stream gate, and active upstream
      response.

## Further reading

- [Python implementation](python/)
- [Node implementation](node/)
- [Java implementation](java/)
- [.NET implementation](dotnet/)
- [00-reference-code](../../00-reference-code/)
- [11-flag-enablement](../../10-code-control/11-flag-enablement/)
- [42-local-if-no-sdk](../../40-dont-do-this/42-local-if-no-sdk/) — the
  opposite anti-pattern: skipping SDK evaluation entirely
