# 24-agent-judges — Python web

Port **8240**. Requires **Python 3.12+**, root `.venv`, `LD_SDK_KEY`, provisioned
completion + judge configs, and local Ollama.

Keywords: **AgentControl** · **Judges** · **create_judge** · **evaluate** · **runtime gate**

| Topic | Docs |
|-------|------|
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| Python AI SDK | [Python AI SDK](https://launchdarkly.com/docs/sdk/ai/python) |
| Spec | [../application.md](../application.md) |

## Prerequisites

```bash
source ../../../.venv/bin/activate
pip install -r ../../../requirements.txt

export LD_SDK_KEY="sdk-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="test"
export LD_API_ACCESS_TOKEN="..."

ollama pull llama3.2:1b    # Toby draft
ollama pull llama3.2:3b    # Charlie rewrite + judges

cd ../rest
./create-judges.sh
./create-config.sh
```

## Build & run

```bash
cd 20-agent-config/24-agent-judges/python
source ../../../.venv/bin/activate
python 24-agent-judges.py
```

Open **http://127.0.0.1:8240/**

## Demo

1. Select **Thoughtless Toby**.
2. **Get Stories** → **Generate AI Report**.
3. Expect decorated Response: **Draft** → **Judge scores (FAIL)** → **Rewrite (Conservative Charlie)**.

## SDK gotcha (Ollama + create_judge)

`create_judge` runs judges through the **OpenAI** AI SDK provider package
(`launchdarkly-server-sdk-ai-openai`), not the Custom/Ollama provider used for
completion drafts.

This app sets:

| Env | Default |
|-----|---------|
| `OPENAI_BASE_URL` | `{OLLAMA_HOST}/v1` (Ollama OpenAI-compatible API) |
| `OPENAI_API_KEY` | `ollama` (dummy; required by the client) |

Drafts still call Ollama’s native `/api/chat`. Judges call Ollama via `/v1`.

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-judged` |
| `LD_JUDGE_FIDELITY_KEY` | No | Default `equity-briefing-source-fidelity` |
| `LD_JUDGE_DISCIPLINE_KEY` | No | Default `equity-briefing-recommendation-discipline` |
| `JUDGE_PASS_THRESHOLD` | No | Default `0.70` |
| `OLLAMA_HOST` | No | Default `http://127.0.0.1:11434` |

Parent: [../README.md](../README.md)
