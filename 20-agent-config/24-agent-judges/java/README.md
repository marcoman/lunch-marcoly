# 24-agent-judges — Java web

Port **8242**. Requires Java **21+**, `LD_SDK_KEY`, provisioned completion + judge
configs, and local Ollama.

**Java has no official AI SDK.** Python uses `completion_config` + `create_judge` /
`evaluate`. Node uses AI SDK 2.x `completionConfig` + `judgeConfig`, then Ollama
JSON for scores. This twin evaluates the same AgentControl keys with the **Java
server SDK** (`jsonValueVariationDetail` / `LDValue`), streams drafts via Ollama
`/api/chat`, and runs judges with **non-streaming Ollama + `format: "json"`**.

Keywords: **AgentControl** · **Judges** · **JSON variation** · **runtime gate** · **Ollama JSON**

| Topic | Docs |
|-------|------|
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| Java server SDK | [Java server-side SDK](https://launchdarkly.com/docs/sdk/server-side/java) |
| Note | Java AI SDK N/A — server SDK JSON + Ollama judge JSON |
| Spec | [../application.md](../application.md) |

## Prerequisites

```bash
export LD_SDK_KEY="sdk-..."
ollama pull llama3.2:1b    # Toby draft
ollama pull llama3.2:3b    # Charlie rewrite + judges

cd ../rest
./create-judges.sh
./create-config.sh
```

## Build & run

```bash
cd 20-agent-config/24-agent-judges/java
./mvnw -q -DskipTests package
java -jar target/24-agent-judges.jar
```

Open **http://127.0.0.1:8242/** (Python twin: **8240**; Node twin: **8241**).

## Demo

1. Select **Thoughtless Toby**.
2. **Get Stories** → **Generate AI Report**.
3. Expect decorated Response: **Draft** → **Judge scores (FAIL)** → **Rewrite (Conservative Charlie)**.

## Java vs Python/Node (judges)

| Step | Python | Node | Java |
|------|--------|------|------|
| Completion config | AI SDK `completion_config` | AI SDK `completionConfig` | `jsonValueVariationDetail` |
| Judges | `create_judge` + `evaluate` | `judgeConfig` + Ollama `format:json` | JSON variation + Ollama `format:json` |
| Judge runner | OpenAI provider → Ollama `/v1` | Native Ollama `/api/chat` | Native Ollama `/api/chat` |
| Generation success | AI SDK tracker | AI SDK tracker | Best-effort `trackMetric` |
| Judge metrics | SDK evaluate | `tracker.trackJudgeResult` | Best-effort `trackMetric` on `$ld:ai:judge:*` |

Prefer Python when the lesson is first-class `create_judge`. Node matches the gate UI on AI SDK 2.x without the OpenAI judge package peer pin.

## Architecture

| File | Role |
|------|------|
| `WebServer.java` | HTTP + SSE |
| `AgentCore.java` | **LD insertion:** JSON variation (completion + judges) → Ollama |
| `YahooNews.java` | Yahoo headlines + `../stories/` cache |
| `src/main/resources/public/index.html` | Browser UI |

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-judged` |
| `LD_JUDGE_FIDELITY_KEY` | No | Default `equity-briefing-source-fidelity` |
| `LD_JUDGE_DISCIPLINE_KEY` | No | Default `equity-briefing-recommendation-discipline` |
| `JUDGE_PASS_THRESHOLD` | No | Default `0.65` |
| `OLLAMA_HOST` | No | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | No | Default `llama3.2:3b` (SDK defaults / judges) |
| `PORT` | No | Default `8242` |

Parent: [../README.md](../README.md) · Spec: [../application.md](../application.md) · Python twin: [../python/README.md](../python/README.md) · Node twin: [../node/README.md](../node/README.md)
