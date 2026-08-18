# 23-agent-tools — .NET web

Port **8233**. Requires **.NET 10 SDK**, `LD_SDK_KEY`, and a provisioned AgentControl config
(`equity-briefing-tools` with Library tools attached). Uses
[`LaunchDarkly.ServerSdk.Ai`](https://launchdarkly.com/docs/sdk/ai/dotnet) (**pre-1.0** on **net10.0**).

- **Analyst Claude** → Anthropic (`ANTHROPIC_API_KEY`)
- **Analyst Llama** → Ollama `llama3.2:3b` (`ollama pull llama3.2:3b`)
- **Analyst Gwen** → Ollama `llama3.2:1b` (smaller; more skips)

Same flow as [Python](../python/) / [Node](../node/): `completionConfig` on `equity-briefing-tools`
returns the model + baseline messages + attached Library tools; this app runs the tool loop
(`analyze-ticker-stories` ×2 → `compare-ticker-analyses`) and streams the briefing over SSE.

Keywords: **AgentControl** · **Library tools** · **CompletionConfig** · **TrackToolCall** · **TrackMetricsOf**

| Topic | Docs |
|-------|------|
| .NET AI SDK | [LaunchDarkly AI SDK for .NET](https://launchdarkly.com/docs/sdk/ai/dotnet) |
| Library tools | [AgentControl tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Provision this config | [../rest/README.md](../rest/README.md) |

## Prerequisites

```bash
export PATH="/usr/local/share/dotnet:$PATH"
export LD_SDK_KEY="sdk-..."
export ANTHROPIC_API_KEY="sk-ant-..."   # Analyst Claude
ollama pull llama3.2:3b                 # Analyst Llama
ollama pull llama3.2:1b                 # Analyst Gwen
```

Provision once: `cd ../rest && ./create-tools.sh && ./create-config.sh`

## Build & run

```bash
cd 20-agent-config/23-agent-tools/dotnet
dotnet restore
dotnet build
dotnet run
```

Open **http://127.0.0.1:8233/** (Python 8230 · Node 8231 · Java 8232).

## What to try

1. **Get Stories** for two tickers.
2. **Analyst Claude** → Anthropic; **Analyst Llama** → `llama3.2:3b`; **Analyst Gwen** → `llama3.2:1b`.
3. Tool trace should show analyze ×2 then compare.
4. Briefing cites headline titles; preferred ticker (if any) matches compare output.

## Architecture

| File | Role |
|------|------|
| `Program.cs` | HTTP + SSE (no feedback route) |
| `AgentCore.cs` | **LD insertion:** `LdAiClient.CompletionConfig` · tool handlers · Anthropic/Ollama tool loops · `tracker.TrackToolCall` / `tracker.TrackMetricsOf` |
| `YahooNews.cs` | Headlines + `../stories/` cache (shared across every language port) |
| `JsonHelpers.cs` | Forgiving `JsonNode` accessors + `LdValue` → `JsonNode` conversion |
| `wwwroot/index.html` | UI + tool trace |

## TrackToolCall / TrackMetricsOf notes (.NET AI SDK 0.12.0)

The .NET AI SDK's shape differs a little from the Python/Node SDKs — worth knowing if you're
porting between languages:

- `LdAiClient.CompletionConfig(configKey, context, defaultConfig, variables)` returns an
  `LdAiCompletionConfig` directly (not a tuple/wrapper) — call `config.CreateTracker()` on it to
  get the `ILdAiConfigTracker` used for both tool and generation tracking.
- **`tracker.TrackToolCall(toolName)`** takes just the tool name — there's no separate
  "call started/finished" pair, and no built-in duration/args/result parameter like some other
  SDKs expose. Call it once, synchronously, right after your own `DispatchTool` returns. Argument
  and result payloads only reach LaunchDarkly if you fold them into your own logging — Monitoring
  only sees that the named tool fired.
- **`tracker.TrackMetricsOf(extractor, asyncFn)`** wraps the provider call and needs an
  `AiMetrics` extractor function you write yourself (`Func<TResponse, AiMetrics>`), not a fixed
  schema — this is how token usage differs between Anthropic (`usage.input_tokens` /
  `output_tokens`) and Ollama (`prompt_eval_count` / `eval_count`) in `AgentCore.cs`. It records
  duration and success/error for you automatically around the call.
- `AiMetrics`/`Usage` are plain records (`Usage(total, input, output)`); there's no
  free-form metadata bag, so anything beyond tokens (e.g. Ollama's `eval_count`) has to be
  aggregated on your own `Metrics` class for the SSE `metrics` event (this port's `Metrics.cs`
  equivalent lives inline in `AgentCore.cs`).
- Java has **no published AI SDK on Maven** yet, so its twin falls back to
  `LDClient.trackMetric` on raw `$ld:ai:tool:call` / `$ld:ai:generation:*` events — the .NET SDK
  gives you the real tracker instead, which is the main reason this port's tool-call/metrics code
  is noticeably shorter than the Java one.

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-tools` |
| `ANTHROPIC_API_KEY` | For Claude | Claude API key |
| `ANTHROPIC_MODEL` | No | Overrides the LD-supplied model when it isn't a `claude*` name |
| `OLLAMA_HOST` | No | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | No | Default `llama3.2:3b` (used only if a persona has no pinned model) |
| `PORT` | No | Fixed at `8233` for this port (see `Program.cs`) |

Parent: [../README.md](../README.md) · Spec: [../application.md](../application.md)
