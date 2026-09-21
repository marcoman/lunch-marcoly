# 60-observability

Learn LaunchDarkly **Observability** on the reference grid navigator, one visible
change at a time.

This series starts with a Python-owned web baseline and then adds the
[LaunchDarkly Python observability plugin](https://launchdarkly.com/docs/sdk/observability/python).
The first instrumented lesson is intentionally narrow: record a manual
OpenTelemetry span for login (with username) and for each successful grid move.

## Examples

| Example | Purpose | Default URL |
|---------|---------|-------------|
| [61-reference](61-reference/) | Server-owned navigator baseline; no LaunchDarkly | [http://127.0.0.1:8610](http://127.0.0.1:8610) |
| [62-server-traces](62-server-traces/) | Add the Python SDK observability plugin; login and successful-move spans | [http://127.0.0.1:8620](http://127.0.0.1:8620) |

Read them in order. Comparing the Python files shows exactly where
observability enters the application.

## Top-level ideas

1. [LaunchDarkly Observability](https://launchdarkly.com/docs/home/observability)
   receives and explores application telemetry.
2. [OpenTelemetry](https://opentelemetry.io/docs/what-is-opentelemetry/) is the
   vendor-neutral model used for traces, metrics, and logs.
3. The [Python observability plugin](https://launchdarkly.com/docs/sdk/observability/python)
   connects the LaunchDarkly server SDK to OpenTelemetry.
4. A [trace](https://launchdarkly.com/docs/home/observability/traces) describes
   work performed by an application. A **span** represents one operation inside
   that trace.
5. [Manual Python spans](https://launchdarkly.com/docs/sdk/features/observability-traces#python)
   let application code mark the exact operation worth inspecting.

## First-time setup

1. Create or open a [LaunchDarkly account](https://app.launchdarkly.com/).
2. Choose a project and environment.
3. Copy that environment's **server-side SDK key**:
   [Projects → Environments](https://launchdarkly.com/docs/home/account/environment/settings#view-environment-credentials).
   Treat it as a secret. Do not use a client-side ID or mobile key.
4. Prepare Python from the repository root:

   ```bash
   pyenv install 3.12       # once, if Python 3.12+ is unavailable
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

5. Run `61-reference` first and verify navigation:

   ```bash
   cd 60-observability/61-reference/python
   python 61-reference.py
   ```

6. Stop it with Ctrl+C. Then export the SDK key and run the traced version:

   ```bash
   export LD_SDK_KEY="sdk-..."
   cd ../../62-server-traces/python
   python 62-server-traces.py
   ```

7. Log in and make several successful moves. The login span includes
   `grid.username`. Boundary presses deliberately produce no span.
8. Open **Observability → Traces** in LaunchDarkly and filter for service
   `lunch-marcoly-62-server-traces` or spans `grid.login` / `grid.move`.

Telemetry can take a short time to appear. Stop the server with Ctrl+C so the
SDK can flush and close cleanly.

## Scope

This first pass covers Python server-side plugin initialization and manual
tracing. Feature flags, browser session replay, errors, logs, custom metrics,
and other languages are later lessons.
