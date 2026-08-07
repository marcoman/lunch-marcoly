# Python web — AgentControl completion config

Same UI as [01-reference-agent](../../../01-reference-agent/python/), but **Generate AI Report** loads **model**, **system**, and **user** messages from LaunchDarkly AgentControl.

Keywords: **AgentControl** · **completion config** · **AI SDK** · **message variables** (`{{ stories }}`)

| Topic | Docs |
|-------|------|
| Python AI SDK | [Python AI SDK reference](https://launchdarkly.com/docs/sdk/ai/python) |
| Customize configs | [Customizing AgentControl configs](https://launchdarkly.com/docs/sdk/features/agentcontrol-config) |
| Provision this config | [../rest/README.md](../rest/README.md) |

## Prerequisites

1. Repo `.venv` + `pip install -r requirements.txt` (includes `launchdarkly-server-sdk-ai`)
2. Provisioned config: `cd ../rest && ./create-config.sh`
3. `LD_SDK_KEY` for the **same environment** as `LD_ENVIRONMENT_KEY` used in targeting
4. Ollama with `llama3.2:3b` (matches `Custom.llama3.2-3b`)

```bash
export LD_SDK_KEY="sdk-..."
# optional: export LD_AGENT_CONFIG_KEY="equity-briefing-completion"
ollama pull llama3.2:3b
```

## Run

```bash
source .venv/bin/activate          # from repo root
cd 20-agent-config/21-agent-completion-config/python
python 21-agent-completion-config.py
```

Open **http://127.0.0.1:8210/** (01 uses 8090).

## What to try

1. **Get Stories** → headline panels fill
2. **Generate AI Report** → User Prompt shows the LD user message (with `{{ stories }}` filled); Response streams from Ollama
3. Provider/model should show `ollama / llama3.2:3b` (from the served variation)
4. Switch users: **Charlie** → `concise-skeptic`; **Nancy** → `baseline-analyst`; **Toby** → `reckless-hype`; **Anonymous Amelia** → fallthrough `baseline-analyst` (anonymous context)
5. Or flip fallthrough only: `../rest/update-targeting.sh concise-skeptic` → regenerate → flip back

## Architecture

| File | Role |
|------|------|
| `21-agent-completion-config.py` | HTTP + SSE |
| `agent_core.py` | **LD insertion:** `completion_config` → Ollama/Bedrock stream |
| `yahoo_news.py` | Yahoo headlines + `../stories/` cache |
| `index.html` | Browser UI |

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-completion` |
| `OLLAMA_HOST` | No | Default `http://127.0.0.1:11434` |
| `AWS_PROFILE` / `AWS_REGION` | For Bedrock models | Only if the variation names a Bedrock model |

## Fallback (config off)

If you **disable** the AgentControl config in LaunchDarkly, the SDK returns `enabled=false` (the disabled variation)—not your SDK default. This app then uses the **in-code baseline-analyst** prompts from [`../rest/messages/baseline-*.txt`](../rest/messages/) plus local Ollama (`OLLAMA_MODEL`, default `llama3.2:3b`).

Provider/model shows `ollama / llama3.2:3b (code baseline)`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Want LD variations again | Turn the config **on** and confirm fallthrough → `baseline-analyst` |
| Missing `LD_SDK_KEY` | Export SDK key for the targeted environment |
| Ollama errors | Daemon up; model id on variation matches `ollama list` |
| Wrong voice after targeting change | Wait a few seconds for stream refresh, then Generate again |

Parent: [../README.md](../README.md) · Spec: [../application.md](../application.md) · Console: [../python-console/README.md](../python-console/README.md)
