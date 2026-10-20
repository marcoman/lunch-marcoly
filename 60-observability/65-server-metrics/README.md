# 65-server-metrics

**Status: stub — not implemented yet.**

A **custom metric** from the Python navigator. **64** stays free between this
lesson and [63-server-errors](../63-server-errors/).

[62-server-traces](../62-server-traces/) does not already do this. That lesson
is two spans for a successful login and a successful move. Documenting 62
more clearly would surface spans, not a metric.

Keywords: **Observability** · **custom metrics** · **OpenTelemetry**

Docs: [Metrics](https://launchdarkly.com/docs/home/observability/metrics)

## Intended aha

Each successful move adds to a metric the app sends on purpose. The screen
shows the metric name and the value it just recorded. Traces stay in 62.
The error-and-log pair stays in 63.

## Direction

- Python first. Intended port **:8650**.
- One metric. A counter of successful moves is enough.
- Do not retarget 62's spans to carry this.

## When implementing

1. `application.md` with the metric name.
2. Start from the 62 plugin setup.
3. The rail shows the metric name after each successful move.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
