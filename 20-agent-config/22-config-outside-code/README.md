# 22-config-outside-code

AgentControl **tracked completion**: model + prompts live in LaunchDarkly, and every generate is wrapped in **`track_metrics_of`** so tokens / success / latency show up in the config **Monitoring** tab. Thumbs up/down send **feedback** via a resumption token.

Templated from [01-reference-agent](../../01-reference-agent/) (same news → generate UI). Sibling of [21-agent-completion-config](../21-agent-completion-config/); 21 teaches completion config + personas; **22 headlines metrics + feedback**.

Inspired by: [Managing AI model configuration outside of code (Node.js)](https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs) — same idea here with Ollama + Anthropic (Python / Node / Java).

## Architecture

The user still generates a briefing from headlines; LaunchDarkly owns the **prompts and model**, and every generate is **tracked** so Monitoring (and thumbs) reflect what actually ran.

```mermaid
flowchart TB
  User["User (analyst)"]
  UI["Web UI :8220 / :8221 / :8222"]
  App["App: completion_config"]
  LD["LaunchDarkly AgentControl<br/>key: equity-briefing-tracked-completion"]
  Track["track_metrics_of"]
  LLM["Ollama or Anthropic"]
  Mon["Monitoring"]
  FB["Thumbs 👍 / 👎"]

  User -->|"Get Stories → Generate"| UI --> App
  App -->|"evaluate (name targeting)"| LD
  LD -->|"variation: model + messages"| App
  App --> Track --> LLM
  Track -->|"tokens / success / latency"| Mon
  LLM -->|"briefing"| User
  User --> FB
  FB -->|"resumption token → feedback"| Mon
```

### LaunchDarkly keys (convenience)

| Kind | Key |
|------|-----|
| AI config | `equity-briefing-tracked-completion` |
| Variation (fallthrough / Amelia) | `tracked-ollama` |
| Variation (Best Betty) | `tracked-anthropic` |

Override with `LD_AGENT_CONFIG_KEY` if needed. Status helper: `./rest/get-feedback-status.sh`.

## Languages

| Language | Port | Status |
|----------|------|--------|
| Python web | **8220** | v1 — `track_metrics_of` + official feedback |
| Node web | **8221** | v1 — same AI SDK path as Python |
| Java web | **8222** | v1 — server SDK eval + Anthropic/Ollama; feedback via `track` (no Java AI SDK yet) |

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

# Python (8220)
cd ../python
source ../../../.venv/bin/activate
python 22-config-outside-code.py

# Node (8221)
cd ../node && npm install && npm start

# Java (8222)
cd ../java && ./mvnw -q -DskipTests package && java -jar target/22-config-outside-code.jar
```

## What to try

1. **Anonymous Amelia** → local Ollama; after generate, check Monitoring + try 👍/👎.
2. **Best Betty** → Anthropic Claude; same metrics + feedback path (Python/Node; Java thumbs use best-effort `track`).
3. Edit prompts on the variation in the LD UI — no code change, no redeploy.

## Docs

- [application.md](application.md) — normative behavior
- [python/README.md](python/README.md) · [node/README.md](node/README.md) · [java/README.md](java/README.md)
- Series: [../README.md](../README.md)
