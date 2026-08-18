# .NET (web)

Web application version of the [01-reference-agent](../application.md) equity briefing demo. **No LaunchDarkly** — this is the baseline the [20-agent-config](../../20-agent-config/) .NET ports (21 / 22 / 23) build on.

Behavior matches the Python / Node / Java web apps: Yahoo headlines → shared system prompt → streamed report (`stub` / `ollama`). Port **8090** (same as the other `01-reference-agent` web languages — run one at a time).

## Prerequisites

- **.NET SDK 10** — `export PATH="/usr/local/share/dotnet:$PATH"` if it's not already on `PATH`
- A modern browser
- Optional: [Ollama](https://ollama.com) for real local LLM text

```bash
export PATH="/usr/local/share/dotnet:$PATH"
dotnet --list-sdks   # expect 10.x
```

### Windows (native)

1. Install [.NET SDK 10](https://dotnet.microsoft.com/download) and ensure `dotnet` is on `PATH`.
2. In PowerShell from this directory:

   ```powershell
   dotnet restore
   dotnet build
   dotnet run
   ```

### Windows with WSL

Prefer building and running **inside WSL** (same as Linux):

```bash
cd ~/code/lunch-marcoly/01-reference-agent/dotnet   # Linux filesystem preferred
export PATH="/usr/local/share/dotnet:$PATH"
dotnet restore
dotnet build
dotnet run
```

Open **http://127.0.0.1:8090/** from a Windows browser.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_LLM_MODE` | `stub` | `stub` \| `ollama` (`bedrock` / `anthropic` reserved, matches Node.js) |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Local Ollama base URL |
| `OLLAMA_MODEL` | `llama3.2:3b` | Ollama model tag |
| `AGENT_LLM_MODEL` | — | Optional override for any mode |
| `PORT` | `8090` | HTTP listen port |

Bedrock is available in the [Python web app](../python/README.md). This .NET example focuses on `stub` and `ollama`, same as the Node.js port.

## Build

```bash
export PATH="/usr/local/share/dotnet:$PATH"
cd 01-reference-agent/dotnet
dotnet restore
dotnet build
```

## Run

```bash
dotnet run
```

Open [http://127.0.0.1:8090/](http://127.0.0.1:8090/). Press Ctrl+C to stop.

### Stub (default)

```bash
dotnet run
```

### Ollama

```bash
ollama pull llama3.2:3b

# macOS / Linux / WSL:
AGENT_LLM_MODE=ollama dotnet run

# Windows PowerShell:
# $env:AGENT_LLM_MODE="ollama"
# dotnet run
```

## What to expect

1. Banner shows `01-reference-agent[dotnet]`.
2. Enter tickers → **Get Stories** → two headline panels fill.
3. **Previous User** / **Next user** only change the selected persona (no LLM).
4. **Generate AI Report** streams into **Response** using [`../prompts/system_prompt.txt`](../prompts/system_prompt.txt).

## Layout

| Path | Role |
|------|------|
| `Program.cs` | Minimal API / Kestrel — HTTP routes + SSE bridge |
| `AgentCore.cs` | Personas, prompt, stub / Ollama generation |
| `YahooNews.cs` | Yahoo Finance + shared [`../stories/stories_cache.json`](../stories/stories_cache.json) (also hosts the internal `JsonUtil` `JsonNode` ⇄ `Dictionary<string, object?>` helpers) |
| `wwwroot/index.html` | Browser UI (shared look/behavior with Node/Python/Java) |
| `../prompts/system_prompt.txt` | Shared system prompt |

## Where LaunchDarkly goes next

This baseline has **no LaunchDarkly SDK, no context, no flag evaluation** — the system prompt is a file and the model provider is `AGENT_LLM_MODE`. Compare `AgentCore.cs` here to [`20-agent-config/21-agent-completion-config/dotnet/AgentCore.cs`](../../20-agent-config/21-agent-completion-config/dotnet/AgentCore.cs): that port replaces the file read + env var with an `LdAiClient.CompletionConfig(...)` evaluation (LaunchDarkly **AgentControl**), same event contract, same UI.

## Related

- [Parent README](../README.md) — overview, architecture diagram, and OS requirements (includes WSL)
- [application.md](../application.md) — full behavior spec
- [python/README.md](../python/README.md) · [node/README.md](../node/README.md) · [java/README.md](../java/README.md) — other web twins
- [20-agent-config/21-agent-completion-config/dotnet/README.md](../../20-agent-config/21-agent-completion-config/dotnet/README.md) — first .NET port that adds LaunchDarkly
