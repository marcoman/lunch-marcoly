# .NET (web)

ASP.NET Minimal API version of [12-flag-variations](../application.md), with an in-app LaunchDarkly Controls / Context / Trace lab.

## Prerequisites

- **.NET SDK 10**
- Provisioned flags and `LD_SDK_KEY`
- For Controls: `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY`

```bash
export PATH="/usr/local/share/dotnet:$PATH"
dotnet --list-sdks   # expect 10.x
export LD_SDK_KEY="sdk-..."
```

On Windows, install [.NET SDK 10](https://dotnet.microsoft.com/download). With WSL, build and run inside WSL.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_API_ACCESS_TOKEN` | For Controls | REST token for semantic-patch controls |
| `LD_PROJECT_KEY` | For Controls | LaunchDarkly project key |
| `LD_ENVIRONMENT_KEY` | For Controls | LaunchDarkly environment key |
| `PORT` | No | Listen port (default `8080`; .NET portal uses `8123`) |

## Build and run

```bash
dotnet build
dotnet run
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

`/api/flags` evaluates boolean, string, number, and JSON variations. The OS emoji uses an anonymous context with private `hostOs`; `maxMoves` comes from `JsonVariation` / `LdValue`.

Documentation: [flag types](https://launchdarkly.com/docs/sdk/features/flag-types) · [anonymous contexts](https://launchdarkly.com/docs/sdk/features/anonymous) · [feature-flag PATCH API](https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag)
