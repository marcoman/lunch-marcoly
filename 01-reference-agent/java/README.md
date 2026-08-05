# Java (web)

Web application version of the [01-reference-agent](../application.md) equity briefing demo.

Behavior matches the Python / Node web apps: Yahoo headlines → shared system prompt → streamed report (`stub` / `ollama`). Port **8090**.

## Prerequisites

- Java **21+**
- Maven Wrapper in this folder (`./mvnw`) — no system Maven install required
- A modern browser
- Optional: [Ollama](https://ollama.com) for real local LLM text

```bash
java -version   # expect 21+
```

### Windows (native)

1. Install a JDK 21+ (Temurin, Oracle, etc.) and ensure `java` is on `PATH`.
2. In PowerShell from this directory:

   ```powershell
   .\mvnw.cmd clean package
   java -jar target\01-reference-agent.jar
   ```

### Windows with WSL

Prefer building and running **inside WSL** (same as Linux):

```bash
sudo apt update
sudo apt install -y openjdk-21-jdk
cd ~/code/lunch-marcoly/01-reference-agent/java   # Linux filesystem preferred
./mvnw clean package
java -jar target/01-reference-agent.jar
```

Open **http://127.0.0.1:8090/** from a Windows browser.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_LLM_MODE` | `stub` | `stub` \| `ollama` (`bedrock` / `anthropic` reserved) |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Local Ollama base URL |
| `OLLAMA_MODEL` | `llama3.2:3b` | Ollama model tag |
| `AGENT_LLM_MODEL` | — | Optional override for any mode |
| `PORT` | `8090` | HTTP listen port |

Bedrock is available in the [Python web app](../python/README.md). This Java example focuses on `stub` and `ollama`.

## Build

From this directory:

```bash
./mvnw clean package
```

Produces a shaded JAR: `target/01-reference-agent.jar`.

## Run

Run from **this directory** so `../prompts/system_prompt.txt` and the shared stories cache resolve correctly:

```bash
java -jar target/01-reference-agent.jar
```

Open [http://127.0.0.1:8090/](http://127.0.0.1:8090/). Press Ctrl+C to stop.

### Stub (default)

```bash
./mvnw clean package
java -jar target/01-reference-agent.jar
```

### Ollama

```bash
ollama pull llama3.2:3b

# macOS / Linux / WSL:
AGENT_LLM_MODE=ollama java -jar target/01-reference-agent.jar

# Windows PowerShell:
# $env:AGENT_LLM_MODE="ollama"
# java -jar target\01-reference-agent.jar
```

## What to expect

1. Banner shows `01-reference-agent[java]`.
2. Enter tickers → **Get Stories** → two headline panels fill.
3. **Previous User** / **Next user** only change the selected persona (no LLM).
4. **Generate AI Report** streams into **Response** using [`../prompts/system_prompt.txt`](../prompts/system_prompt.txt).

## Layout

| Path | Role |
|------|------|
| `src/main/java/WebServer.java` | HTTP + SSE |
| `src/main/java/AgentCore.java` | Personas, prompt, stub / Ollama |
| `src/main/java/YahooNews.java` | Yahoo Finance + shared [`../stories/stories_cache.json`](../stories/stories_cache.json) |
| `src/main/resources/public/index.html` | Browser UI |
| `../prompts/system_prompt.txt` | Shared system prompt |

## Related

- [Parent README](../README.md) — overview and OS requirements
- [application.md](../application.md) — full behavior spec
- [python/README.md](../python/README.md) · [node/README.md](../node/README.md)
