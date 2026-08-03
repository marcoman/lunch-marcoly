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

- Python 3.12+ with repository virtual environment (for the first implementation)
- Optional: local [Ollama](https://ollama.com/) for `AGENT_LLM_MODE=ollama`

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
| `OLLAMA_MODEL` | `llama3.1:8b` | Model tag |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | — | Bedrock |
| `AGENT_BEDROCK_MODEL_ID` | — | Bedrock model id |
| `ANTHROPIC_API_KEY` | — | Anthropic |
| `ANTHROPIC_MODEL` | — | Optional override |

Full table: [application.md](application.md#configuration-environment-variables).

## Try it (Python web)

```bash
cd python
python 01-reference-agent.py
```

Open http://127.0.0.1:8090/ — stub mode runs with no API keys.
