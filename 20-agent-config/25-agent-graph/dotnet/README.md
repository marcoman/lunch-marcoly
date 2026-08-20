# 25-agent-graph — .NET web

Port **8253**. Requires .NET **10**, `LD_SDK_KEY`, a provisioned agent graph +
node configs, and local Ollama.

Keywords: **AgentControl** · **Agent graphs** · **Agents** · **handoffs** · **Library tools**

| Topic | Docs |
|-------|------|
| Agent graphs | [Agent graphs](https://launchdarkly.com/docs/home/agentcontrol/agent-graphs) |
| Agents | [Agents](https://launchdarkly.com/docs/home/agentcontrol/agents) |
| Tools | [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| .NET AI SDK | [.NET AI SDK](https://launchdarkly.com/docs/sdk/ai/dotnet) |
| Spec | [../application.md](../application.md) |

## Prerequisites

```bash
export LD_SDK_KEY="sdk-..."
ollama pull llama3.2:3b

cd ../rest
./create-all.sh   # graph + six agent-mode nodes (assess/report/questions/good/joke/finalize)
```

## Build & run

```bash
cd 20-agent-config/25-agent-graph/dotnet
dotnet run
```

Open **http://127.0.0.1:8253/** (Python: **8250**; Node: **8251**; Java: **8252**).

## Architecture

| File | Role |
|------|------|
| `Program.cs` | HTTP + SSE |
| `AgentCore.cs` | **LD insertion:** `LdAiClient.AgentGraph` + `AgentConfig` → manual walk → Ollama |
| `YahooNews.cs` | Yahoo headlines + `../stories/` cache |
| `wwwroot/index.html` | Browser UI (Trace dock + mini path map) |

## What to click

| Button | Stories? | Path |
|--------|----------|------|
| Generate AI Report | Required | assess → report → finalize |
| Identify questions | Required | assess → questions → finalize |
| Identify good & bad | Required | assess → good → finalize (## Good / ## Bad) |
| Tell me a joke | Optional | assess → joke → finalize (+ humor %; higher temp for variety) |

Humor easter egg (code-only): Charlie 25% · Amelia 50% · Toby 90%.

## SDK note (manual walk, not automatic orchestration)

`AgentCore.GenerateStreamAsync` evaluates the graph once via
`LdAiClient.AgentGraph(graphKey, context)`, then evaluates each node via
`LdAiClient.AgentConfig(nodeKey, context, default, variables)` and calls Ollama
itself. After **assess**, the chosen specialist (and later **finalize**) must
match an outgoing edge on the evaluated `AgentGraphDefinition` — checked with
`GetChildNodes(sourceKey)`. Invalid handoffs redirect to `report` (or the first
valid child) and are recorded with `AiGraphTracker.TrackHandoffFailure` /
`TrackRedirect`; valid handoffs record `TrackHandoffSuccess`. The full node
path is recorded once via `TrackPath`.

Scorer tools (`score-question-gap`, `score-joke-corny`) are app-invoked Ollama
JSON calls for Trace visibility — they never rewrite the specialist output.
Each call is recorded with `ILdAiConfigTracker.TrackToolCall` and the score is
embedded in the Trace tool *name* (e.g. `score-question-gap:0.82`).

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_GRAPH_KEY` | No | Default `equity-briefing-graph` |
| `LD_NODE_ASSESS` | No | Default `equity-briefing-graph-assess` |
| `LD_NODE_REPORT` | No | Default `equity-briefing-graph-report` |
| `LD_NODE_QUESTIONS` | No | Default `equity-briefing-graph-questions` |
| `LD_NODE_GOOD` | No | Default `equity-briefing-graph-good` |
| `LD_NODE_JOKE` | No | Default `equity-briefing-graph-joke` |
| `LD_NODE_FINALIZE` | No | Default `equity-briefing-graph-finalize` |
| `OLLAMA_HOST` | No | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | No | Default `llama3.2:3b` |
| `JOKE_TEMPERATURE` | No | Default `0.95`, clamped to `[0, 1.5]` |
| `JOKE_CORNY_HIGH` | No | Default `0.80` |
| `JOKE_CORNY_LOW` | No | Default `0.20` |
| `PORT` | No | Default `8253` |

Parent: [../README.md](../README.md) · Spec: [../application.md](../application.md) · Python: [../python/README.md](../python/README.md)
