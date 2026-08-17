# 23-agent-tools

AgentControl **Library tools** on a completion config: the model must call
`analyze-ticker-stories` once per ticker, then `compare-ticker-analyses`, then
write a briefing grounded in headline evidence. Handlers are deterministic in
app code; schemas live in LaunchDarkly.

Sibling of [22-config-outside-code](../22-config-outside-code/) (metrics/feedback)
and [21-agent-completion-config](../21-agent-completion-config/) (completion + targeting).

Docs: [Tools](https://launchdarkly.com/docs/home/agentcontrol/tools) ·
[Python AI SDK](https://launchdarkly.com/docs/sdk/ai/python)

## Languages (this cut)

| Language | Port | Status |
|----------|------|--------|
| Python web | **8230** | v1 |
| Node / Java | — | later |

## Config + tools

| | |
|--|--|
| Config key | `equity-briefing-tools` |
| Mode | completion |
| Variation | `tools-anthropic` → `claude-sonnet-5` |
| Tool 1 | `analyze-ticker-stories` |
| Tool 2 | `compare-ticker-analyses` |

**Analyst Claude** uses Anthropic (`ANTHROPIC_API_KEY`). **Analyst Llama** uses local Ollama `llama3.2:3b`. **Analyst Gwen** uses `llama3.2:1b` (smaller / flakier). Personas are **local UI/runtime choices** — not LaunchDarkly name targeting.

Local models may skip tools; the Python Ollama loop nudges and can force `compare-ticker-analyses` from prior analyze results so the lesson still shows. Prefer Claude for a clean demo.

## Quick start

```bash
export LD_SDK_KEY=sdk-...
export LD_PROJECT_KEY=lunch-marcoly
export LD_ENVIRONMENT_KEY=test
export LD_API_ACCESS_TOKEN=...
export ANTHROPIC_API_KEY=sk-ant-...   # Analyst Claude
# Local Ollama personas:
#   ollama pull llama3.2:3b   # Analyst Llama
#   ollama pull llama3.2:1b   # Analyst Gwen

cd rest
./create-config.sh   # also creates tools + attaches + sets fallthrough

cd ../python
source ../../../.venv/bin/activate
python 23-agent-tools.py
# Open http://127.0.0.1:8230/
```

## What to try

1. **Get Stories** for two tickers.
2. **Analyst Claude** → Anthropic; **Analyst Llama** → `llama3.2:3b`; **Analyst Gwen** → `llama3.2:1b`.
3. Tool trace should show analyze ×2 then compare.
4. Briefing cites headline titles; preferred ticker (if any) matches compare output.
5. Check the config **Monitoring** tab for tool-call events — or run
   `./rest/get-tools-status.sh` (Library · attach · generations).

## Docs

- [application.md](application.md)
- [python/README.md](python/README.md)
- [rest/README.md](rest/README.md)
- Series: [../README.md](../README.md)
