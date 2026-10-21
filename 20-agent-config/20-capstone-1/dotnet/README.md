# 20-capstone — .NET web

Same capstone as the Node app: assess → specialist → judges → checked tools → finalize.

Port **8293**. Requires the .NET 10 SDK, `LD_SDK_KEY`, the capstone graph and node configs, and local Ollama.

Keywords: **AgentControl** · **agent graphs** · **Library tools** · **judges** · **TrackToolCall** · **TrackFeedback** · **locale**

| Topic | Docs |
|-------|------|
| Agent graphs | [Agent graphs](https://launchdarkly.com/docs/home/agentcontrol/agent-graphs) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| AI metrics / feedback | [Tracking AI metrics](https://launchdarkly.com/docs/sdk/features/ai-metrics) |
| .NET AI SDK | [.NET AI SDK](https://launchdarkly.com/docs/sdk/ai/dotnet) |
| Spec | [../application.md](../application.md) |

## Run

```bash
export LD_SDK_KEY="sdk-..."
export PATH="/usr/local/share/dotnet:$PATH"
ollama pull llama3.2:3b

cd 20-agent-config/20-capstone/dotnet
dotnet run
```

Open **http://127.0.0.1:8293/**.

The screen matches the Node app. Provision the graph once from `../rest`. This app is not a portal tab.

## LaunchDarkly

The insertion points are in `AgentCore.cs`:

- `LdAiClient.AgentGraph` then `AgentConfig` per node
- `JudgeConfig` on the specialist draft, before tools
- `TrackToolCall` for each checked tool, on the specialist tracker
- `CreateTracker` + `TrackFeedback` from that specialist resumption token
