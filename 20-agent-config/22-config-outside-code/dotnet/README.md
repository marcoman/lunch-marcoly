# 22-config-outside-code — .NET web

Port **8223**. Requires .NET **10.0 SDK**, `LD_SDK_KEY`, and (for Best Betty) `ANTHROPIC_API_KEY`.

Full parity twin of the Node/Python implementations: evaluates the AgentControl completion
config with the **AI SDK** (`LdAiClient.CompletionConfig`), calls Ollama/Anthropic, wraps the
call in **`TrackMetricsOf`**, and records thumbs with **`TrackFeedback`** via a resumption
token — same LaunchDarkly surface as Node's `trackMetricsOf` / `trackFeedback`.

Keywords: **AgentControl** · **completion config** · **`TrackMetricsOf`** · **`TrackFeedback`** · **resumption token**

| Topic | Docs |
|-------|------|
| .NET AI SDK | [LaunchDarkly AI SDK for .NET](https://launchdarkly.com/docs/sdk/ai/dotnet) |
| Pattern guide (Node) | [Config outside code](https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs) |
| Provision this config | [../rest/README.md](../rest/README.md) |

## Prerequisites

```bash
export PATH="/usr/local/share/dotnet:$PATH"
export LD_SDK_KEY="sdk-..."
export ANTHROPIC_API_KEY="sk-ant-..."   # Best Betty
ollama pull llama3.2:1b                 # Anonymous Amelia / fallthrough
```

Provision once: `cd ../rest && ./create-config.sh && ./update-name-targeting.sh`

## Build & run

```bash
cd 20-agent-config/22-config-outside-code/dotnet
dotnet restore
dotnet build
dotnet run
```

Open **http://127.0.0.1:8223/** (Python 8220 · Node 8221 · Java 8222).

## What to try

1. **Anonymous Amelia** → Ollama `llama3.2:1b` (fallthrough variation)
2. **Best Betty** → Anthropic `claude-sonnet-5` (name-targeted variation)
3. Watch **Monitoring** in LaunchDarkly for generation metrics (`TrackMetricsOf`: latency, TTFT, token usage)
4. Thumbs up/down after a response fires **`TrackFeedback`** against the same generation, via the resumption token returned in the SSE `done` event

## Architecture

| File | Role |
|------|------|
| `Program.cs` | HTTP + SSE + `/api/feedback` |
| `AgentCore.cs` | **LD insertion:** `LdAiClient.CompletionConfig` · `TrackMetricsOf` · `TrackFeedback` |
| `YahooNews.cs` | Headlines + `../stories/` cache |
| `wwwroot/index.html` | UI + thumbs |

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-tracked-completion` |
| `ANTHROPIC_API_KEY` | For Betty | Claude API key |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | For Ollama | Default model `llama3.2:1b` |
| `PORT` | No | Default `8223` |

Parent: [../README.md](../README.md) · Spec: [../application.md](../application.md)
