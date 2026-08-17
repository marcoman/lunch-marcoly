# 22-config-outside-code

AgentControl **tracked completion**: model + prompts live in LaunchDarkly, and every generate is wrapped in **`track_metrics_of`** so tokens / success / latency show up in the config **Monitoring** tab. Thumbs up/down send **feedback** via a resumption token.

Templated from [01-reference-agent](../../01-reference-agent/) (same news → generate UI). Sibling of [21-agent-completion-config](../21-agent-completion-config/); 21 teaches completion config + personas; **22 headlines metrics + feedback**.

Inspired by: [Managing AI model configuration outside of code (Node.js)](https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs) — same idea, Python-first, Anthropic instead of OpenAI.

## Languages (this cut)

| Language | Port | Status |
|----------|------|--------|
| Python web | **8220** | v1 |
| Node / Java | — | later |

## Config

| | |
|--|--|
| Key | `equity-briefing-tracked-completion` |
| Mode | completion |
| Fallthrough | `tracked-ollama` → `llama3.2:1b` |
| Best Betty | `tracked-anthropic` → `claude-sonnet-5` |

## Quick start

```bash
# Series setup (SDK key, Ollama) — see ../README.md
export LD_SDK_KEY=sdk-...
export LD_PROJECT_KEY=lunch-marcoly
export LD_ENVIRONMENT_KEY=test   # or production
export LD_API_ACCESS_TOKEN=...

# Provision once
cd rest
./create-config.sh
./update-name-targeting.sh

# Ollama (Anonymous Amelia / fallthrough)
ollama pull llama3.2:1b

# Anthropic (Best Betty) — optional but required for that persona
export ANTHROPIC_API_KEY=sk-ant-...

cd ../python
source ../../../.venv/bin/activate
python 22-config-outside-code.py
# Open http://127.0.0.1:8220/
```

## What to try

1. **Anonymous Amelia** → local Ollama; after generate, check Monitoring + try 👍/👎.
2. **Best Betty** → Anthropic Claude; same metrics + feedback path.
3. Edit prompts on the variation in the LD UI — no code change, no redeploy.

## Docs

- [application.md](application.md) — normative behavior
- [python/README.md](python/README.md) — run notes
- Series: [../README.md](../README.md)
