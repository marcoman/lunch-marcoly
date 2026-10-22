# 605-server-metrics

**Status: stub — not implemented yet.**

A **custom metric** from the Python navigator. **604** stays free between this
lesson and [603-server-errors](../603-server-errors/).

[602-server-traces](../602-server-traces/) does not already do this. That lesson
is two spans for a successful login and a successful move. Documenting 602
more clearly would surface spans, not a metric.

Keywords: **Observability** · **custom metrics** · **OpenTelemetry**

Docs: [Metrics](https://launchdarkly.com/docs/home/observability/metrics)

## Intended aha

Each successful move adds to a metric the app sends on purpose. The screen
shows the metric name and the value it just recorded. Traces stay in 602.
The error-and-log pair stays in 603.

## Direction

- Python first. Intended port **:8650**.
- One metric. A counter of successful moves is enough.
- Do not retarget 602's spans to carry this.

## When implementing

1. `application.md` with the metric name.
2. Start from the 602 plugin setup.
3. The rail shows the metric name after each successful move.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
