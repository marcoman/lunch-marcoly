# 62-server-traces

Add LaunchDarkly Observability to [61-reference](../61-reference/): a
manual server-side span for each **successful login** and each **successful**
grid move.

Keywords: **Observability** · **OpenTelemetry** · **traces** · **spans** ·
**ObservabilityPlugin**

## What changes from 61

1. Initialize the LaunchDarkly Python server SDK with
   [`ObservabilityPlugin`](https://launchdarkly.com/docs/sdk/observability/python).
2. Wrap a successful login in
   [`observe.start_span`](https://launchdarkly.com/docs/sdk/features/observability-traces#python)
   and attach `grid.username`.
3. Wrap a successful move in the same API with direction and old/new positions.

The Python source marks these additions with large
`BEGIN/END LAUNCHDARKLY OBSERVABILITY` comment blocks. Everything outside those
blocks is the baseline application.

## First-time setup

### 1. Understand the two pieces

- The [LaunchDarkly Python server SDK](https://launchdarkly.com/docs/sdk/server-side/python)
  opens the authenticated SDK connection.
- The [observability plugin](https://launchdarkly.com/docs/sdk/observability/python)
  configures OpenTelemetry and exports telemetry to LaunchDarkly.

This example evaluates no feature flags, but the plugin still belongs on the
server SDK configuration.

### 2. Get the correct credential

In LaunchDarkly, choose a project and environment, then copy the environment's
**server-side SDK key** from
[Projects → Environments](https://launchdarkly.com/docs/home/account/environment/settings#view-environment-credentials).

Do not use a client-side ID, mobile key, or API access token. Never commit the
SDK key.

### 3. Install dependencies

From the repository root:

```bash
pyenv install 3.12       # once, if needed
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The relevant packages are `launchdarkly-server-sdk>=9.12` and
`launchdarkly-observability`.

### 4. Run

```bash
export LD_SDK_KEY="sdk-..."
cd 60-observability/62-server-traces/python
python 62-server-traces.py
```

Open [http://127.0.0.1:8620/](http://127.0.0.1:8620/).

### 5. Produce traces

1. Enter a username. That login creates a `grid.login` span with
   `grid.username`.
2. Move with arrow keys or WASD.
3. Make several moves that change the selected cell.
4. Press against an edge and notice that a blocked move is intentionally not
   traced.

### 6. Inspect LaunchDarkly

Open [LaunchDarkly Observability](https://launchdarkly.com/docs/home/observability),
then:

1. Select **Traces**.
2. Filter service name to `lunch-marcoly-62-server-traces`.
3. Find spans named `grid.login` and `grid.move`.
4. On `grid.login`, inspect `grid.username`. On `grid.move`, inspect
   `grid.direction`, `grid.from`, and `grid.to`.

Telemetry may take a short time to arrive. Stop with Ctrl+C to flush and close
the SDK.

## Environment variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `LD_SDK_KEY` | Yes | — | Environment server-side SDK key |
| `PORT` | No | `8620` | Local HTTP port |
| `SERVICE_VERSION` | No | `development` | OpenTelemetry service version |

## What is intentionally absent

No flags, browser SDK, session replay, error capture, log correlation, or
custom metrics. Two spans, still a small lesson.
