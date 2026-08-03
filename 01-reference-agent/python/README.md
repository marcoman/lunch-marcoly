# Python (web)

Web application for [01-reference-agent](../application.md).

## Architecture — how to follow the code

Read the files in this order; each layer has a single job:

```
index.html                 Browser UI + SSE client
        │
        ▼  GET /api/bootstrap , GET /api/generate (SSE)
01-reference-agent.py      Thin HTTP adapter (stdlib ThreadingHTTPServer)
        │
        ▼  generate_stream(persona)
agent_core.py              Personas, prompts, providers, metrics
```

| File | Role |
|------|------|
| `agent_core.py` | Domain logic: personas, canned input, profile instructions, stub/Ollama providers, event stream. No HTTP. |
| `01-reference-agent.py` | HTTP only: static page, bootstrap JSON, SSE bridge to `generate_stream()`. |
| `index.html` | Single screen: persona nav, input/response, provider, metrics, status. |

### Request flow (one generation)

1. Browser calls `GET /api/generate?personaId=…`.
2. Server looks up the persona and calls `generate_stream(persona)`.
3. Core emits events in order: `meta` → `token*` → optional `error` → `metrics` → `done`.
4. Server wraps each event as `data: {json}\n\n` (SSE).
5. Browser appends tokens, then fills metrics / status.

Persona changes only the **system** instructions. The **user** message is always the same canned input.

## Prerequisites

- Python **3.12+** via [pyenv](https://github.com/pyenv/pyenv)
- Repository virtual environment activated (stub mode needs no extra packages)

From the repository root:

```bash
pyenv install 3.12    # once, if needed
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `AGENT_LLM_MODE` | `stub` | `stub` or `ollama` (bedrock/anthropic reserved) |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Local Ollama |
| `OLLAMA_MODEL` | `llama3.1:8b` | Model tag |

AWS / Anthropic env vars are documented in [application.md](../application.md) for later provider wiring.

## Build

No compile step. Stub and Ollama modes use the Python standard library only.

## Run

```bash
python 01-reference-agent.py
```

Open [http://127.0.0.1:8090/](http://127.0.0.1:8090/). Press Ctrl+C to stop.

Optional Ollama:

```bash
AGENT_LLM_MODE=ollama OLLAMA_MODEL=llama3.1:8b python 01-reference-agent.py
```

## What to expect

1. Screen opens on **Conservative Charlie** and streams a stub response.
2. **Next** / **Previous** cycle Neutral Nancy and Thoughtless Toby (auto-generate).
3. **Refresh** re-runs the current persona with the same canned input.
4. Provider/model and metrics update when the stream finishes; errors appear in Status.
