# 16-percentage-rollout — .NET web

.NET 10 Minimal API implementation of
[16-percentage-rollout](../application.md).

Keywords: **percentage rollout** · **context key** · **sticky bucketing**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)

## Run

```bash
export LD_SDK_KEY="sdk-..."
cd 10-code-control/16-percentage-rollout/dotnet
dotnet run --project 16-percentage-rollout.csproj
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/). `PORT` overrides the
default. The .NET portal tab 16 uses **:8163**.

Provision the dedicated `pct` flag with the sibling [REST](../rest/) example.
