# .NET web — 16-adaptive-triggers

ASP.NET Minimal API twin of the Node adaptive-trigger grid. The process owns
`LD_SDK_KEY` and REST credentials; none are sent to the browser.

LaunchDarkly surfaces: **string variation**, **numeric custom `track` event**,
and **adaptive trigger** variation switching.

- https://launchdarkly.com/docs/home/flags/triggers
- https://launchdarkly.com/docs/sdk/features/events

## Prerequisites

- **.NET SDK 10**
- Provision [`../rest/`](../rest/) and configure the adaptive trigger in the UI

```bash
export PATH="/usr/local/share/dotnet:$PATH"
dotnet --list-sdks   # expect 10.x
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
```

On Windows, install [.NET SDK 10](https://dotnet.microsoft.com/download). With
WSL, build and run inside WSL.

## Build and run

```bash
dotnet restore
dotnet build
dotnet run
```

Open [http://127.0.0.1:8161/](http://127.0.0.1:8161/). `PORT` overrides the
default. `LD_APP_HOST` overrides the dashboard deep-link host and defaults to
`LD_API_HOST`.

## Demo

1. Log in and click **Start live (green)**.
2. Confirm `Flag value: green`.
3. Set latency above 200 ms and enable **Auto-report once per second**.
4. After the alert window, watch the **Default rule** card record `green → none`.
5. Click **Stop** to turn targeting off.

The slider reports a numeric value without delaying navigation. Adaptive
triggers are environment-specific: the status rail warns when `LD_SDK_KEY`
belongs to a different environment than `LD_ENVIRONMENT_KEY`.

Single evaluation:

```bash
dotnet run -- --evaluate-once robot
```
