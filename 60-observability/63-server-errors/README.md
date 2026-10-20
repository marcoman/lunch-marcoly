# 63-server-errors

**Status: stub — not implemented yet.**

One **deliberate error** on the Python navigator. It shows up as an
Observability **error** and as a **log line**. Logs do not get a separate
example. **64** stays free.

[62-server-traces](../62-server-traces/) records successful `grid.login` and
`grid.move` spans. It does not emit this error. Leave those spans as they are.

Keywords: **Observability** · **errors** · **logs** · **OpenTelemetry**

Docs: [Errors](https://launchdarkly.com/docs/home/observability/errors) ·
[Logs](https://launchdarkly.com/docs/home/observability/logs)

## Intended aha

A button (or a known bad move) throws once. The page says the error was sent.
In LaunchDarkly, that same failure is an error event and a log line, so the
runner can find both from one action.

## Direction

- Python first, same navigator shape as 61 and 62. Intended port **:8630**.
- One error. Do not also invent a metrics lesson here. That is
  [65-server-metrics](../65-server-metrics/).
- The error is deliberate and labeled in the UI.

## When implementing

1. `application.md` naming the error and the log message.
2. Start from 62 so the plugin is already initialized.
3. The rail tells the runner where to look: Errors, and Logs.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
