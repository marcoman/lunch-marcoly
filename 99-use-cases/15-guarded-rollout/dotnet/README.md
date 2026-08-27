# .NET (web)

ASP.NET Minimal API grid navigator for [15-guarded-rollout](../application.md).
The process owns `LD_SDK_KEY`; it is not sent to the browser.

This web twin evaluates the highlight flag only. Full guardrail exercise
(`--exercise-once`) remains in [python-console](../python-console/).

LaunchDarkly: **string variation** and **guarded rollout**.
https://launchdarkly.com/docs/home/releases/guarded-rollouts
https://launchdarkly.com/docs/sdk/features/evaluations

## Prerequisites

- **.NET SDK 10**
- `LD_SDK_KEY` for the target environment

```bash
export PATH="/usr/local/share/dotnet:$PATH"
dotnet --list-sdks   # expect 10.x
export LD_SDK_KEY="sdk-..."
```

On Windows, install [.NET SDK 10](https://dotnet.microsoft.com/download). With
WSL, build and run inside WSL.

## Build and run

```bash
dotnet restore
dotnet build
dotnet run
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/). `PORT` overrides the
default. The page polls the flag every 500 ms.

Single evaluation:

```bash
dotnet run -- --evaluate-once alice
```
