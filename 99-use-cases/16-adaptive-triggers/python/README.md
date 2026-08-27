# Python web — 16-adaptive-triggers

Python twin of the Node adaptive-trigger grid. The process owns the server-side
SDK key and REST access token; neither credential is sent to the browser.

LaunchDarkly surfaces: **string variation**, **numeric custom `track` event**,
and **adaptive trigger** variation switching.

- https://launchdarkly.com/docs/home/flags/triggers
- https://launchdarkly.com/docs/sdk/features/events

## Configure and run

Provision [`../rest/`](../rest/) first, configure the adaptive trigger in the
LaunchDarkly UI, then set the variables shown in [`.env.example`](.env.example).
The file is documentation rather than an automatically loaded dotenv file.

```bash
python -m pip install -r requirements.txt
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
python 16-adaptive-triggers.py
```

Open http://127.0.0.1:8161/. `PORT` overrides the default. `LD_APP_HOST`
overrides the dashboard deep-link host and defaults to `LD_API_HOST`.

## Demo

1. Log in and click **Start live (green)**.
2. Confirm the evaluated flag value is `green`.
3. Set latency above 200 ms and enable **Auto-report once per second**.
4. After the configured alert window, observe the default rule switch to
   `none`, including history and audit attribution in the rail.
5. Click **Stop** to turn targeting off.

The slider reports a numeric value without delaying navigation. Adaptive
triggers are environment-specific: the status rail warns when `LD_SDK_KEY`
belongs to a different environment than `LD_ENVIRONMENT_KEY`.

Single evaluation:

```bash
python 16-adaptive-triggers.py --evaluate-once robot
```
