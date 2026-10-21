# .NET web

Same three-column briefing as [Python](../python/). **Generate AI Report** runs AgentControl, Separate flags, and JSON flag.

Completion uses `CompletionConfig`, which substitutes `{{ stories }}`. Flags use `JsonVariationDetail`. The guardrail uses `JudgeConfig`, then a local Ollama JSON score. A failed AgentControl draft runs `reduce-briefing-uncertainty` when that tool is attached (`TrackToolCall`). Python uses `create_judge`; this port stays on the same teaching gate as Node and the 24 .NET app.

Keywords: **feature flags** · **JSON variations** · **AgentControl** · **completion config** · **judges** · **Library tools**

| Topic | Docs |
|-------|------|
| .NET AI SDK | [.NET AI SDK](https://launchdarkly.com/docs/sdk/ai/dotnet) |
| Flag types | [Flag types](https://launchdarkly.com/docs/sdk/features/flag-types) |
| Evaluation reasons | [Evaluation reasons](https://launchdarkly.com/docs/sdk/features/evaluation-reasons) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |

## Run

```bash
export LD_SDK_KEY="sdk-..."
export PATH="/usr/local/share/dotnet:$PATH"
cd 20-agent-config/26-flags-vs-agent-control/dotnet
dotnet run
```

Open **http://127.0.0.1:8263/**. Requires .NET 10. Provision first with [../rest/README.md](../rest/README.md).

Python is **8260**. Node is **8261**. Java is **8262**.
