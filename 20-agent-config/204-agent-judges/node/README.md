# 24-agent-judges — Node.js web

Port **8241**. Requires Node **20+**, `LD_SDK_KEY`, provisioned completion + judge
configs, and local Ollama.

Keywords: **AgentControl** · **Judges** · **judgeConfig** · **runtime gate** · **Ollama JSON**

| Topic | Docs |
|-------|------|
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| Node AI SDK | [Node.js AI SDK](https://launchdarkly.com/docs/sdk/ai/node-js) |
| Spec | [../application.md](../application.md) |

## Prerequisites

```bash
nvm use
export LD_SDK_KEY="sdk-..."
ollama pull llama3.2:1b
ollama pull llama3.2:3b
cd ../rest && ./create-judges.sh && ./create-config.sh
```

## Build & run

```bash
cd 20-agent-config/24-agent-judges/node
npm install
npm start
```

Open **http://127.0.0.1:8241/** (Python twin: **8240**; Java twin: **8242**).

## Demo

1. **Thoughtless Toby** → Get Stories → Generate.
2. Expect decorated Response: Draft → failing judge scores → Charlie rewrite.

## SDK note (judgeConfig vs createJudge)

Completion uses AI SDK **2.x** `completionConfig` (same as 21/23). Judges use
`judgeConfig` for prompts/model from LaunchDarkly, then **Ollama `/api/chat` with
`format: "json"`** for the gate scores.

`createJudge` needs `@launchdarkly/server-sdk-ai-openai`, which still peers AI SDK
`^1.x` — not used here so this example can stay on AI SDK 2.x. Python still shows
first-class `create_judge` + OpenAI-compat → Ollama `/v1`.

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-judged` |
| `LD_JUDGE_FIDELITY_KEY` | No | Default `equity-briefing-source-fidelity` |
| `LD_JUDGE_DISCIPLINE_KEY` | No | Default `equity-briefing-recommendation-discipline` |
| `JUDGE_PASS_THRESHOLD` | No | Default `0.65` |
| `OLLAMA_HOST` | No | Default `http://127.0.0.1:11434` |
| `PORT` | No | Default `8241` |

Parent: [../README.md](../README.md)
