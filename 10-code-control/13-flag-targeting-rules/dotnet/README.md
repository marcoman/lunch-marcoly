# .NET (web)

.NET 10 Minimal API implementation of
[13-flag-targeting-rules](../application.md). The SDK evaluates a public `team`
context attribute, omitted entirely for No team.

## Run

```bash
dotnet build 13-flag-targeting-rules.csproj
dotnet run --project 13-flag-targeting-rules.csproj
```

Set `LD_SDK_KEY` for evaluation. Controls also require
`LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY`.
`PORT` defaults to `8080`.

Controls change flag on/off and fallthrough only; targeting rules come from the
sibling [Terraform](../terraform/) or [REST](../rest/) provisioning.
