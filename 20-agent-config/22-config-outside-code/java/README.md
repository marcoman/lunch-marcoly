# 22-config-outside-code — Java web

Port **8222**. Requires Java 21+, `LD_SDK_KEY`, and (for Best Betty) `ANTHROPIC_API_KEY`.

**Java has no published AI SDK on Maven yet.** Python/Node use `completionConfig` + `trackMetricsOf` + official resumption tokens. This twin evaluates the same AgentControl key with the **server SDK** (`jsonValueVariationDetail`), calls Ollama/Anthropic, and records thumbs with **`LDClient.trackMetric`** on `$ld:ai:feedback:*` (metric value `1`, same as Node `trackFeedback`). Prefer Python/Node when the lesson is Monitoring generation-metrics parity.

Keywords: **AgentControl** · **completion config** · **JSON variation** · **feedback** (best-effort)

| Topic | Docs |
|-------|------|
| Java server SDK | [Java server-side SDK](https://launchdarkly.com/docs/sdk/server-side/java) |
| Pattern guide (Node) | [Config outside code](https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs) |
| Provision this config | [../rest/README.md](../rest/README.md) |

## Prerequisites

```bash
export LD_SDK_KEY="sdk-..."
export ANTHROPIC_API_KEY="sk-ant-..."   # Best Betty
ollama pull llama3.2:1b                 # Anonymous Amelia / fallthrough
```

Provision once: `cd ../rest && ./create-config.sh && ./update-name-targeting.sh`

## Build & run

```bash
cd 20-agent-config/22-config-outside-code/java
./mvnw -q -DskipTests package
java -jar target/22-config-outside-code.jar
```

Open **http://127.0.0.1:8222/** (Python 8220 · Node 8221).

## What to try

1. **Anonymous Amelia** → Ollama `llama3.2:1b`; thumbs fire `$ld:ai:feedback:*`
2. **Best Betty** → Anthropic `claude-sonnet-5` when `ANTHROPIC_API_KEY` is set
3. For full **Monitoring** generation metrics via `trackMetricsOf`, use [../python](../python/) or [../node](../node/)

## Architecture

| File | Role |
|------|------|
| `WebServer.java` | HTTP + SSE + `/api/feedback` |
| `AgentCore.java` | **LD insertion:** `jsonValueVariationDetail` · Anthropic/Ollama · `track` feedback |
| `YahooNews.java` | Headlines + `../stories/` cache |
| `src/main/resources/public/index.html` | UI + thumbs |

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-tracked-completion` |
| `ANTHROPIC_API_KEY` | For Betty | Claude API key |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | For Ollama | Default model `llama3.2:1b` |
| `PORT` | No | Default `8222` |

Parent: [../README.md](../README.md) · Spec: [../application.md](../application.md)
