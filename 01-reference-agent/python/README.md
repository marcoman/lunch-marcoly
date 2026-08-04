# Python (web)

Web application for [01-reference-agent](../application.md).

## Architecture — how to follow the code

Read the files in this order; each layer has a single job:

```
index.html                 Browser UI + SSE client + ticker/story panels
        │
        ▼  GET /api/bootstrap , /api/stories , /api/generate (SSE)
01-reference-agent.py      Thin HTTP adapter (stdlib ThreadingHTTPServer)
        │
        ├─ yahoo_news.py   Yahoo Finance headlines (2 tickers × 2 stories)
        └─ agent_core.py   Personas, prompts, providers, metrics
```

| File | Role |
|------|------|
| `yahoo_news.py` | Fetch latest headlines for two tickers from Yahoo Finance. |
| `agent_core.py` | Domain logic: personas, story-based prompts, stub/Ollama/Bedrock providers, event stream. No HTTP. |
| `01-reference-agent.py` | HTTP only: static page, bootstrap JSON, stories API, SSE bridge. |
| `index.html` | Tickers, Get Stories, story panels, persona nav, response, metrics, status. |

### Request flow (one generation)

1. Browser calls `GET /api/generate?personaId=…`.
2. Server looks up the persona and calls `generate_stream(persona)`.
3. Core emits events in order: `meta` → `token*` → optional `error` → `metrics` → `done`.
4. Server wraps each event as `data: {json}\n\n` (SSE).
5. Browser appends tokens, then fills metrics / status.

Persona changes only the **system** instructions. The **user** message is always the same canned input.

## Prerequisites

- Python **3.12+** via [pyenv](https://github.com/pyenv/pyenv) (see [root README](../../README.md#python-and-pyenv))
- A **Python virtual environment** at the repository root (`.venv`) — do not install into the system Python

Use the **repository-root** [`requirements.txt`](../../requirements.txt) (there is no per-example `requirements.txt`). Stub / Ollama modes only need the standard library; **Bedrock** needs `boto3` from that same file. Always install into the repository `.venv`.

From the repository root:

```bash
pyenv install 3.12    # once, if needed
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Activate `.venv` whenever you work on this example.

## Environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `AGENT_LLM_MODE` | `stub` | `stub`, `ollama`, or `bedrock` |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Local Ollama |
| `OLLAMA_MODEL` | `llama3.1:8b` | Model tag |
| `AWS_PROFILE` | `Administrator` | SSO profile in `~/.aws/config` (`aws sso login --profile Administrator`) |
| `AWS_REGION` | `us-east-1` | Also accepts `AWS_DEFAULT_REGION` |
| `AGENT_BEDROCK_MODEL_ID` | `us.amazon.nova-lite-v1:0` | Default report model (Nova Lite) |

Recommended report / prose models (all general-purpose text — fine for reports):

| Model | Id |
|-------|----|
| Nova Lite | `us.amazon.nova-lite-v1:0` |
| Claude Haiku 4.5 | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Qwen3 32B | `qwen.qwen3-32b-v1:0` |

Avoid coding-specialized ids (e.g. `qwen.qwen3-coder-*`) for this use case.

Bedrock auth uses the SSO profile `Administrator`. Shell key
exports are ignored for Bedrock so the SSO session wins. See
[application.md](../application.md#aws-bedrock).

## Build

No compile step. Dependencies come from the repository root `requirements.txt` (see above).

## Run

From this directory, with `.venv` active:

```bash
python 01-reference-agent.py
```

Open [http://127.0.0.1:8090/](http://127.0.0.1:8090/). Press Ctrl+C to stop.

Optional Ollama:

```bash
AGENT_LLM_MODE=ollama OLLAMA_MODEL=llama3.1:8b python 01-reference-agent.py
```

Optional Bedrock:

```bash
export AWS_REGION=us-east-1
export AGENT_LLM_MODE=bedrock
# optional: export AGENT_BEDROCK_MODEL_ID=qwen.qwen3-32b-v1:0
python 01-reference-agent.py
```
## What to expect

1. Screen opens on **Conservative Charlie** and streams a stub response.
2. **Next** / **Previous** cycle Neutral Nancy and Thoughtless Toby (auto-generate).
3. **Refresh** re-runs the current persona with the same canned input.
4. Provider/model and metrics update when the stream finishes; errors appear in Status.
