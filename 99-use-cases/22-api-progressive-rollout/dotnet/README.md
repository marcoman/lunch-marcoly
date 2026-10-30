# .NET web — 22-api-progressive-rollout

Grid navigator for [22-api-progressive-rollout](../application.md).

The page evaluates `api-progressive-grid-highlight`. **Start progressive release** POSTs the environment release. Python is **:8780**. This process is **:8783**.

```bash
dotnet run
```

Open http://127.0.0.1:8783/ . `PORT` overrides the listen port.

```bash
dotnet run -- --evaluate-once alice
```

[Environment releases (beta)](https://launchdarkly.com/docs/api/environment-releases)
