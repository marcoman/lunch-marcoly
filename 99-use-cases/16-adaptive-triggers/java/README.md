# Java web — 16-adaptive-triggers

Server-side LaunchDarkly Java SDK evaluation with the browser grid and the full
adaptive-trigger lab rail. The Java process owns `LD_SDK_KEY` and all REST
credentials; none are sent to the page.

LaunchDarkly surfaces: **string variation**, **contexts**, **numeric custom
`track` event**, **audit log**, and **adaptive trigger** variation switching.

- https://launchdarkly.com/docs/home/flags/triggers
- https://launchdarkly.com/docs/sdk/features/events
- https://launchdarkly.com/docs/api/audit-log/get-audit-log-entries

## Prerequisites

- Java **21+**
- Provision [../rest/](../rest/) and configure the adaptive trigger in the UI

Export the server-side configuration:

```bash
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
```

## Build and run

```bash
./mvnw clean package
java -jar target/16-adaptive-triggers.jar
```

Open [http://127.0.0.1:8161/](http://127.0.0.1:8161/). `PORT` overrides the
default. `LD_APP_HOST` overrides the dashboard host used for deep links and
defaults to `LD_API_HOST`.

The static UI in `src/main/resources/public/index.html` is a standalone copy
of the Node lab page with `[java]` branding. It includes Start/Stop,
auto-report, default-rule history, audit attribution, environment diagnostics,
and dashboard links.

## Demo

1. Log in and click **Start live (green)**.
2. Confirm `Flag value: green`.
3. Set the latency above 200 ms and enable **Auto-report once per second** for
   the full adaptive-trigger alert window.
4. Watch the **Default rule** card record `green → none` and attribute the last
   change to LaunchDarkly automation.
5. Click **Stop** to turn targeting off.

The slider reports a numeric metric value; it does not delay navigation.
Adaptive triggers are environment-specific. The status rail warns when the SDK
key sends events to a different environment than `LD_ENVIRONMENT_KEY`.

## Single evaluation

```bash
java -jar target/16-adaptive-triggers.jar --evaluate-once robot
```

With no `LD_SDK_KEY`, this safely prints the `none` code fallback.
