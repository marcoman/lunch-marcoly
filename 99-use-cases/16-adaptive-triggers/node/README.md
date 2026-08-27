# Node web — 16-adaptive-triggers

Server-rendered LaunchDarkly evaluation with a browser grid and lab controls.
The Node process owns `LD_SDK_KEY` and REST credentials; none are sent to the
page.

LaunchDarkly surfaces: **string variation**, **numeric custom `track` event**,
and **adaptive trigger** variation switching.

- https://launchdarkly.com/docs/home/flags/triggers
- https://launchdarkly.com/docs/sdk/features/events

## Prerequisites

Provision [../rest/](../rest/) first, configure the adaptive trigger in the UI,
then export:

```bash
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
```

## Build and run

```bash
nvm use
npm install
npm start
```

Open [http://127.0.0.1:8161/](http://127.0.0.1:8161/). `PORT` overrides the
default.

`LD_APP_HOST` overrides the dashboard host used for deep links; it defaults to
`LD_API_HOST`.

## Demo

1. Log in and click **Start live (green)**.
2. Confirm `Flag value: green`.
3. Move with the slider at 50 ms; numeric events remain under the threshold.
4. Set the slider above 200 ms, then enable **Auto-report once per second** so
   the metric receives a steady stream for the full alert window.
5. LaunchDarkly switches the default variation to `none`. The grid updates
   within about 500 ms, and the **Default rule** card logs the switch.
6. Click **Stop** to turn targeting off and return to the provisioned default.
   Remove the adaptive trigger in the dashboard if you want a clean slate.

Latency must stay above the threshold for the trigger's whole alert window.
Prefer a 1 minute window when configuring the trigger; a 30 minute window means
a 30 minute demo.

## Default rule card

The rail polls `/api/status` every 5 seconds and shows:

- the variation the default rule currently serves, and whether targeting is on
- a timestamped history of observed switches, such as `20:41:03 green → none`
- attribution of the most recent flag change from the audit log

Attribution is the tell. A change you caused reads as your API token name;
a trigger-driven change has no member or token actor.

The slider reports a value; it deliberately does not sleep or slow the app.
The event log records `track`, not repeated `variation` calls.

The rail links to the flag's **Targeting** tab (where the adaptive trigger is
configured) and **Monitoring** tab (evaluations and metric analytics), plus the
metric and the environment list.

## Troubleshooting a trigger that does not fire

| Symptom in the rail | Meaning |
|---------------------|---------|
| `SDK not initialized` | `LD_SDK_KEY` is missing or invalid; no metric events are sent. |
| `Environment mismatch` | `LD_SDK_KEY` belongs to a different environment than `LD_ENVIRONMENT_KEY`. Adaptive triggers are environment-specific, so events never reach the trigger. |
| `Flag OFF` | Targeting is off, so there is no live variation to switch away from. |

Flag **evaluation** counts are not metric event counts. This page polls the
server about twice per second, and each poll is a server-side `variation` call,
so evaluations climb quickly even when no metric events are sent. Compare the
rail's `N tracked` counter against the metric page instead.

If diagnostics are clean, check in the LaunchDarkly UI that the adaptive trigger
exists on this environment, is enabled, uses the
`adaptive-grid-nav-latency-metric` metric, and that its alert window has fully
elapsed with data. A trigger that already fired stays in cooldown.

Single evaluation:

```bash
node 16-adaptive-triggers.js --evaluate-once robot
```
