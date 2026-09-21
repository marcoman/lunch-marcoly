# 62-server-traces application specification

This application preserves the complete
[61-reference contract](../61-reference/application.md) and adds LaunchDarkly
server-side observability.

## LaunchDarkly surface

- [Python observability plugin](https://launchdarkly.com/docs/sdk/observability/python)
- [Manual traces and spans](https://launchdarkly.com/docs/sdk/features/observability-traces#python)
- OpenTelemetry service name: `lunch-marcoly-62-server-traces`
- Span names: `grid.login`, `grid.move`

## Instrumentation rules

Create one `grid.login` span when `POST /api/login` accepts a non-empty
username. Attach:

| Attribute | Value |
|-----------|-------|
| `grid.username` | Trimmed username from the request |

Create one `grid.move` span only when `POST /api/move` changes the current
position. Attach:

| Attribute | Value |
|-----------|-------|
| `grid.direction` | `up`, `down`, `left`, or `right` |
| `grid.from` | Previous `{row}/{col}` |
| `grid.to` | New `{row}/{col}` |

Do not put SDK keys or raw request bodies in span attributes. Username is
recorded on `grid.login` only — that is the teaching point for this addition.

Blocked boundary moves, empty-username login failures, logout, state reads, and
quit are intentionally not manually traced. Automatic instrumentation emitted
by the plugin may still describe supported library activity.

## Code-teaching requirement

Every observability insertion in Python must be enclosed by conspicuous:

```text
# === BEGIN LAUNCHDARKLY OBSERVABILITY: ... ===
...
# === END LAUNCHDARKLY OBSERVABILITY: ... ===
```

comments and include the relevant official documentation link.
