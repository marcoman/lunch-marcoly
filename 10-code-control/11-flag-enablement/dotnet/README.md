# .NET (web)

ASP.NET Minimal API version of the [11-flag-enablement grid navigator](../application.md), with server-side LaunchDarkly evaluation and an in-app Controls / Context / Trace lab.

## Prerequisites

- **.NET SDK 10**
- Provisioned flags and `LD_SDK_KEY`
- For Controls: `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY`

```bash
export PATH="/usr/local/share/dotnet:$PATH"
dotnet --list-sdks   # expect 10.x
export LD_SDK_KEY="sdk-..."
```

On Windows, install [.NET SDK 10](https://dotnet.microsoft.com/download) and ensure `dotnet` is on `PATH`. With WSL, build and run inside WSL.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |
| `LD_API_ACCESS_TOKEN` | For Controls | REST token for semantic-patch controls |
| `LD_PROJECT_KEY` | For Controls | LaunchDarkly project key |
| `LD_ENVIRONMENT_KEY` | For Controls | LaunchDarkly environment key |
| `PORT` | No | Listen port (default `8080`; .NET portal uses `8113`) |

## Build and run

```bash
dotnet build
dotnet run
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

The four feature flags cover a string highlight variation, boolean color override, move count, and host OS emoji. The `hostOs` context attribute is private. Controls use LaunchDarkly semantic patches (`turnFlagOn`, `turnFlagOff`, and fallthrough updates).

Documentation: [contexts](https://launchdarkly.com/docs/home/flags/contexts) · [private attributes](https://launchdarkly.com/docs/sdk/features/private-attributes) · [feature-flag PATCH API](https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag)
