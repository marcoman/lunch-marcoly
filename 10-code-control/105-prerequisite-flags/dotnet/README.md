# .NET (web)

.NET 10 Minimal API implementation of
[15-prerequisite-flags](../application.md). The LaunchDarkly .NET server SDK
evaluates parent and child flags independently so an unmet
[prerequisite](https://launchdarkly.com/docs/home/flags/prereqs) shows up as
`PREREQUISITE_FAILED`.

## Run

```bash
dotnet build 15-prerequisite-flags.csproj
dotnet run --project 15-prerequisite-flags.csproj
```

Set `LD_SDK_KEY` for evaluation. Controls also require
`LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY`.
`PORT` defaults to `8080`.

Provision the `-prereq` flags with the sibling [REST](../rest/) example.
Controls never edit the prerequisite relationship.
