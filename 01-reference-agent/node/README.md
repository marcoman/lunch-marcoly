# Node.js (web)

Web application version of the [01-reference-agent](../application.md) equity briefing demo.

Behavior matches the [Python web app](../python/): Yahoo headlines → shared system prompt → streamed report (`stub` / `ollama`). Port **8090**.

## Prerequisites

- [nvm](https://github.com/nvm-sh/nvm) (recommended)
- Node.js 20 LTS+ (pinned in the repository root [`.nvmrc`](../../.nvmrc))
- A modern browser
- Optional: [Ollama](https://ollama.com) for real local LLM text

From the **repository root**, before working in this folder:

```bash
nvm install
nvm use
node -v    # expect v20.x
```

### Windows (native)

1. Install [nvm-windows](https://github.com/coreybutler/nvm-windows) or a Node 20 installer.
2. Open PowerShell in the repository root:

   ```powershell
   nvm use 20
   cd 01-reference-agent\node
   npm start
   ```

### Windows with WSL

Prefer running Node **inside WSL** (same as Linux), not from `/mnt/c` if you can avoid it:

```powershell
wsl --install
```

In the Ubuntu (WSL) shell:

```bash
# install nvm, then:
cd ~/code/lunch-marcoly   # or your clone path on the Linux filesystem
nvm install
nvm use
cd 01-reference-agent/node
npm start
```

Open **http://127.0.0.1:8090/** from a Windows browser (WSL port forwarding usually exposes it automatically).

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_LLM_MODE` | `stub` | `stub` \| `ollama` (`bedrock` / `anthropic` reserved) |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Local Ollama base URL |
| `OLLAMA_MODEL` | `llama3.2:3b` | Ollama model tag |
| `AGENT_LLM_MODEL` | — | Optional override for any mode |

Bedrock is available in the [Python web app](../python/README.md). This Node example focuses on `stub` and `ollama`.

## Build

No npm dependencies. Optional:

```bash
npm install
```

## Run

```bash
cd 01-reference-agent/node
node 01-reference-agent.js
# or: npm start
```

Open [http://127.0.0.1:8090/](http://127.0.0.1:8090/). Press Ctrl+C to stop.

### Stub (default)

```bash
npm start
```

### Ollama

```bash
ollama pull llama3.2:3b

# macOS / Linux / WSL:
AGENT_LLM_MODE=ollama npm start

# Windows PowerShell:
# $env:AGENT_LLM_MODE="ollama"
# npm start
```

## What to expect

1. Banner shows `01-reference-agent[node]`.
2. Enter tickers → **Get Stories** → two headline panels fill.
3. **Previous User** / **Next user** only change the selected persona (no LLM).
4. **Generate AI Report** streams into **Response** using [`../prompts/system_prompt.txt`](../prompts/system_prompt.txt).

## Layout

| Path | Role |
|------|------|
| `01-reference-agent.js` | HTTP + SSE |
| `agentCore.js` | Personas, prompt, stub / Ollama |
| `yahooNews.js` | Yahoo Finance + shared [`../stories/stories_cache.json`](../stories/stories_cache.json) |
| `index.html` | Browser UI |
| `../prompts/system_prompt.txt` | Shared system prompt |

## Related

- [Parent README](../README.md) — overview and OS requirements (includes WSL)
- [application.md](../application.md) — full behavior spec
- [python/README.md](../python/README.md) — Python twin (includes Bedrock)
