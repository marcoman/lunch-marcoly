# .NET (web)

.NET 10 Minimal API implementation of
[14-multi-context-targeting](../application.md). The SDK evaluates
`show-partner-org-badge` against a
[multi-context](https://launchdarkly.com/docs/home/flags/multi-contexts)
(`user` + `organization`).

## Run

```bash
dotnet build 14-multi-context-targeting.csproj
dotnet run --project 14-multi-context-targeting.csproj
```

Set `LD_SDK_KEY` for evaluation. Controls also require
`LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY`.
`PORT` defaults to `8080`.

Controls change flag on/off and fallthrough only; targeting rules come from the
sibling [REST](../rest/) provisioning.

```bash
python ../collect-results.py --url http://127.0.0.1:8080
```
