# 62-server-traces — Python web

The `61-reference` server-owned navigator plus LaunchDarkly's Python
observability plugin, a `grid.login` span, and a `grid.move` span.

## Prerequisites

- Python **3.12+**
- A LaunchDarkly environment **server-side SDK key**
- Repository `.venv` with dependencies installed

For credential and installation walkthroughs, start with the
[series README](../../README.md#first-time-setup).

## Environment variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `LD_SDK_KEY` | Yes | — | LaunchDarkly environment server-side SDK key |
| `PORT` | No | `8620` | Local HTTP port |
| `SERVICE_VERSION` | No | `development` | OpenTelemetry service version |

## Build and run

From the repository root:

```bash
source .venv/bin/activate
export LD_SDK_KEY="sdk-..."
cd 60-observability/62-server-traces/python
python 62-server-traces.py
```

Open [http://127.0.0.1:8620/](http://127.0.0.1:8620/).

## What to expect

A successful login creates a `grid.login` span with `grid.username`. Each move
that changes position creates a `grid.move` span with direction, origin, and
destination. Blocked edge moves do not create manual spans. View them under
LaunchDarkly **Observability → Traces**, filtering on service
`lunch-marcoly-62-server-traces`.

The Python file encloses every LaunchDarkly addition in
`BEGIN/END LAUNCHDARKLY OBSERVABILITY` block comments for a clean comparison
with `61-reference.py`.
