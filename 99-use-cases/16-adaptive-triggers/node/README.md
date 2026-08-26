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

## Demo

1. Log in and click **Start live (green)**.
2. Confirm `Flag value: green`.
3. Move with the slider at 50 ms; numeric events remain under the threshold.
4. Set the slider above 200 ms and keep moving for the full trigger window.
5. LaunchDarkly switches the default variation to `none`; polling updates the
   grid within about 500 ms.

The slider reports a value; it deliberately does not sleep or slow the app.
The event log records `track`, not repeated `variation` calls.

Single evaluation:

```bash
node 16-adaptive-triggers.js --evaluate-once robot
```
