# 23-agent-tools — Java web

Port **8232**. Requires Java 21+, `LD_SDK_KEY`, and (for Analyst Claude) `ANTHROPIC_API_KEY`.

**Java has no published AI SDK on Maven yet.** Python/Node use `completionConfig` + `track_tool_call` + `trackMetricsOf`. This twin evaluates the same AgentControl key with the **server SDK** (`jsonValueVariationDetail`), runs the tool loop in-app, and records tool calls with **`LDClient.trackMetric`** on `$ld:ai:tool:call` (best-effort; see parity notes below). Generation success/error uses `$ld:ai:generation:success` / `$ld:ai:generation:error` the same way as [22-config-outside-code Java](../22-config-outside-code/java/).

Keywords: **AgentControl** · **Library tools** · **tool loop** · **track_tool_call** (best-effort)

| Topic | Docs |
|-------|------|
| Library tools | [AgentControl tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Java server SDK | [Java server-side SDK](https://launchdarkly.com/docs/sdk/server-side/java) |
| Provision this config | [../rest/README.md](../rest/README.md) |

## Prerequisites

```bash
export LD_SDK_KEY="sdk-..."
export ANTHROPIC_API_KEY="sk-ant-..."   # Analyst Claude
ollama pull llama3.2:3b                 # Analyst Llama
ollama pull llama3.2:1b                 # Analyst Gwen
```

Provision once: `cd ../rest && ./create-config.sh`

## Build & run

```bash
cd 20-agent-config/23-agent-tools/java
./mvnw -q -DskipTests package
java -jar target/23-agent-tools.jar
```

Open **http://127.0.0.1:8232/** (Python 8230 · Node 8231).

## What to try

1. **Get Stories** for two tickers.
2. **Analyst Claude** → Anthropic; **Analyst Llama** → `llama3.2:3b`; **Analyst Gwen** → `llama3.2:1b`.
3. Tool trace should show analyze ×2 then compare.
4. Briefing cites headline titles; preferred ticker (if any) matches compare output.

## Architecture

| File | Role |
|------|------|
| `WebServer.java` | HTTP + SSE (no feedback route) |
| `AgentCore.java` | **LD insertion:** `jsonValueVariationDetail` · tool handlers · Anthropic/Ollama tool loops · `trackMetric` |
| `YahooNews.java` | Headlines + `../stories/` cache |
| `src/main/resources/public/index.html` | UI + tool trace |

## Parity notes (Java vs Python/Node)

| Capability | Python/Node | Java |
|------------|-------------|------|
| Config evaluation | AI SDK `completionConfig` | `jsonValueVariationDetail` |
| Tool loop | In app | In app (same handlers) |
| `track_tool_call` | AI SDK tracker | Best-effort `trackMetric` on `$ld:ai:tool:call` with `toolName` + `configKey` |
| Generation metrics | `trackMetricsOf` | Best-effort `$ld:ai:generation:success` / `error` |
| Thumbs feedback | N/A in 23 | N/A in 23 |

Prefer Python/Node when the lesson is first-class Monitoring parity (`track_tool_call`, `trackMetricsOf`).

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-tools` |
| `ANTHROPIC_API_KEY` | For Claude | Claude API key |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | For Ollama | Default model `llama3.2:3b` |
| `PORT` | No | Default `8232` |

Parent: [../README.md](../README.md) · Spec: [../application.md](../application.md)
