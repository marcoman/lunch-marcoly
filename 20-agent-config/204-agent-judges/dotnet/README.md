# 24-agent-judges — .NET web

Port **8243**. Requires .NET **10**, `LD_SDK_KEY`, provisioned completion + judge
configs, and local Ollama.

Keywords: **AgentControl** · **Judges** · **JudgeConfig** · **runtime gate** · **Ollama JSON**

| Topic | Docs |
|-------|------|
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| .NET AI SDK | [.NET AI SDK](https://launchdarkly.com/docs/sdk/ai/dotnet) |
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
cd 20-agent-config/24-agent-judges/dotnet
dotnet run
```

Open **http://127.0.0.1:8243/** (Python: **8240**; Node: **8241**; Java: **8242**).

## Demo

1. Select **Thoughtless Toby**.
2. **Get Stories** → **Generate AI Report**.
3. Expect decorated Response: **Draft** → **Judge scores (FAIL)** → **Rewrite (Conservative Charlie)**.

## SDK note (JudgeConfig, no CreateJudge)

Completion uses `LdAiClient.CompletionConfig` (same as 21). Judges use
`LdAiClient.JudgeConfig` for prompts/model/metric from LaunchDarkly, then
**Ollama `/api/chat` with `format: "json"`** for the gate scores.

This example does **not** call CreateJudge — same teaching gate as the Node twin
(Python still shows first-class `create_judge` + OpenAI-compat → Ollama `/v1`).

After each Ollama score: `tracker.TrackJudgeResult(new JudgeResult(...))`.

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
| `PORT` | No | Default `8243` |

Parent: [../README.md](../README.md) · Spec: [../application.md](../application.md) · Python: [../python/README.md](../python/README.md) · Node: [../node/README.md](../node/README.md)
