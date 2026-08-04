# 01-reference-agent

Single-screen **reference agent** UI: fixed personas, shared canned prompt, streamed LLM (or stub) responses, provider/model display, and standard LLM metrics.

This example is the LLM baseline (config / env only). LaunchDarkly AgentControl / AI Config arrives in later variations.

See [application.md](application.md) for the full behavior specification.

## What this demonstrates

- Persona navigation (Previous / Next) with auto-generate
- Refresh to re-run the same input
- Streaming responses
- Stub mode (`default-no-llm`) for UI testing without credentials
- Pluggable provider modes: stub → Ollama → Bedrock → Anthropic

## Prerequisites

- Python 3.12+ via pyenv, plus a repository-root virtual environment (`.venv`)
- Install deps from the **root** [`requirements.txt`](../requirements.txt) — see [python/README.md](python/README.md)
- Optional: local [Ollama](https://ollama.com/) for `AGENT_LLM_MODE=ollama`
- Optional: AWS credentials + region for `AGENT_LLM_MODE=bedrock`

## Language implementations

| Language | Directory | Application type | Status |
|----------|-----------|------------------|--------|
| Python | [python/](python/) | Web | First |
| Python | [python-console/](python-console/) | Console | Planned next |
| Node.js | — | Web / console | Later |
| Java | — | Web / console | Later |
| Go | — | Console | Later |
| Rust | — | Console (REST) | Later |
| C++ | — | — | Likely omitted |

## Environment variables (summary)

| Variable | Default | Notes |
|----------|---------|-------|
| `AGENT_LLM_MODE` | `stub` | `stub` \| `ollama` \| `bedrock` \| `anthropic` |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Local Ollama |
| `OLLAMA_MODEL` | `llama3.2:3b` | Model tag |
| `AWS_PROFILE` | `Administrator` | Recommended Bedrock auth (AWS SSO profile) |
| `AWS_REGION` | `us-east-1` | Bedrock region |
| `AGENT_BEDROCK_MODEL_ID` | Nova Lite id | e.g. Haiku 4.5 or Qwen3 32B |
| `ANTHROPIC_API_KEY` | — | Anthropic |
| `ANTHROPIC_MODEL` | — | Optional override |

Full table: [application.md](application.md#configuration-environment-variables).

## Try it (Python web)

From the repository root (once):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then:

```bash
cd 01-reference-agent/python
python 01-reference-agent.py
```

Open http://127.0.0.1:8090/ — stub mode runs with no API keys.

Bedrock (AWS SSO profile `Administrator`):

```bash
aws sso login --profile Administrator
export AWS_REGION=us-east-1
export AGENT_LLM_MODE=bedrock
python 01-reference-agent.py
```

`AWS_PROFILE` defaults to `Administrator`. Re-run `aws sso login` when the SSO session expires.
