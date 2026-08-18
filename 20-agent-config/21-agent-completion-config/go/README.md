# Go (console)

Terminal UI twin of the [python-console](../python-console/), matching the [01-reference-agent Go console](../../../01-reference-agent/go/) chrome and hotkeys. Same LaunchDarkly **AgentControl** generate path as the other language ports (`CompletionConfig` → model + system/user messages); fixed hotkey chrome instead of a browser.

Keywords: **AgentControl** · **completion config** · **Go AI SDK** · **message variables** (`{{ stories }}`)

| Topic | Docs |
|-------|------|
| Go AI SDK | [Go AI SDK reference](https://launchdarkly.com/docs/sdk/ai/go) |
| Customize configs | [Customizing AgentControl configs](https://launchdarkly.com/docs/sdk/features/agentcontrol-config) |
| AI metrics | [Tracking AI metrics](https://launchdarkly.com/docs/sdk/features/ai-metrics) |
| Provision this config | [../rest/README.md](../rest/README.md) |

## Prerequisites

- Go **1.24+**
- Interactive TTY
- Provisioned config: `cd ../rest && ./create-config.sh`
- `LD_SDK_KEY` for the targeted environment
- **Required:** all three Ollama tags ([parent README](../README.md#required-ollama-models))

```bash
export LD_SDK_KEY="sdk-..."
# optional: export LD_AGENT_CONFIG_KEY="equity-briefing-completion"
ollama pull llama3.2:3b    # required — Charlie (best)
ollama pull gemma2:2b      # required — Nancy / Amelia (default)
ollama pull llama3.2:1b    # required — Toby (simple)
ollama list
```

## Build

From this directory:

```bash
go mod tidy
go build -o 21-agent-completion-config .
```

## Run

Run from **this directory** so `../rest/messages/` (baseline fallback prompts) and `../stories/` (shared Yahoo cache) resolve:

```bash
./21-agent-completion-config
```

Without `LD_SDK_KEY` (or if LaunchDarkly is unreachable, or the config is turned off), generate still works — it falls back to the in-code **baseline-analyst** prompts (`../rest/messages/baseline-*.txt`) against local Ollama. A `status`-kind line in the output pane says so.

## Screen chrome

```text
21-agent-completion-config[go]                Tickers: NVDA (2 stories) SPCX (2 stories)
config:equity-briefing-completion                        Name: Conservative Charlie.
(t)ickers  st(o)ries  (s)tatus  (g)enerate report  (q)uit                  (n)ext user
```

Before the first generate, the middle row shows `config:equity-briefing-completion`. After generate, it shows the **served** provider/model (e.g. `ollama / llama3.2:3b`).

| Key | Action |
|-----|--------|
| `t` | Set two tickers |
| `o` | Fetch Yahoo headlines (shared `../stories/` cache) |
| `s` | Status: user, tickers, config key, served provider/model, last LD variation + stories |
| `g` | Generate — LD evaluate → stream report |
| `n` | Next persona (wrap; no LLM call until `g`) |
| `q` | Quit |
| `↑` `↓` `PgUp` `PgDn` | Scroll output |

No `(m)ode` hotkey here — unlike [01 go](../../../01-reference-agent/go/), the served AgentControl variation owns provider + model. There is nothing local to cycle.

Typical session: `o` → `g` → `s` → `n` → `g` (compare personas) → `q`.

## What to expect

1. **Generate** prints `LD: <variationKey>  config=<key>`, then `Provider: <provider> / <model>`, the full **Prompt** (the AgentControl **user** message, `{{ stories }}` already substituted), then streams the **Response** (cyan).
2. Switch personas: **Charlie** → `concise-skeptic` (llama3.2:3b) · **Nancy** → `baseline-analyst` (gemma2:2b) · **Toby** → `reckless-hype` (llama3.2:1b) · **Anonymous Amelia** → fallthrough `baseline-analyst` (gemma2:2b, anonymous context — no name targeting can match).
3. **`s`** shows a one-line `Last LD: variation=… fallback=…` alongside the ops snapshot.

## Architecture

| File | Role |
|------|------|
| `main.go` | Raw-terminal TUI (chrome, hotkeys, scrollback) — adapted from [01-reference-agent/go/main.go](../../../01-reference-agent/go/main.go) |
| `agent.go` | **LD insertion:** `aiClient.CompletionConfig(...)` → stream. See the file header for the full read-order. |
| `yahoo.go` | Yahoo headlines + shared `../stories/` cache — unchanged from [01-reference-agent/go/yahoo.go](../../../01-reference-agent/go/yahoo.go) |

## Go AI SDK note (API quirks vs Python / Node / .NET)

The Go AI SDK is **pre-1.0** and lags the other AI SDKs. Two module paths exist and only one has `CompletionConfig`:

| Module | Package | Has `CompletionConfig`? |
|--------|---------|--------------------------|
| `github.com/launchdarkly/go-server-sdk-ai` (**used here**) | `ldai` | Yes — `AICompletionConfig`, `AICompletionConfigDefault`, `datamodel.Message`/`Role` |
| `github.com/launchdarkly/go-server-sdk/ldai` (bundled in server-sdk v7) | `ldai` | No — only a generic, mode-agnostic `Config()` |

This example imports the **separate** `go-server-sdk-ai` module (aliased `ld` in `agent.go`) specifically for `CompletionConfig`, matching the task's instruction to prefer it over the deprecated generic `Config`.

Other differences from the Python/Node/.NET ports:

- **No second evaluation call for variation metadata.** Python and .NET re-evaluate the same flag key with the plain server SDK's JSON variation API to read `_ldMeta.variationKey` (the typed config doesn't expose it in those SDKs). The Go `AICompletionConfig` exposes `VariationKey()` and `Version()` directly (deprecated as "internal", but usable) — no second call needed.
- **No explicit network-failure branch.** `CompletionConfig()` never returns an error; on any failure (bad key, unreachable LD) it silently returns your supplied default. This example detects that case by checking `config.VariationKey() == ""` (empty only on the default path) in addition to `!config.Enabled()`, folding both into one `usingFallback` check — see `generateStream()` in `agent.go`.
- **Messages come back as `[]datamodel.Message`** (`Role`/`Content`, JSON-tagged), which is passed straight through to Ollama's `/api/chat` — no reshaping needed.
- **Metrics via `Tracker`**: `config.CreateTracker()` → `TrackSuccess`/`TrackError`, `TrackDuration`, `TrackTimeToFirstToken`, `TrackTokens(ldai.TokenUsage{...})`. Same shape as Python's `create_tracker()` / .NET's `CreateTracker()`.

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes (else falls back to code baseline) | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-completion` |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | For Custom/Ollama variations | `OLLAMA_MODEL` only backs the code-baseline fallback; served variations carry their own model |

## Related

- [../python-console/README.md](../python-console/README.md) — curses twin (adds `(l)d` LD-details drawer)
- [../README.md](../README.md) — example landing
- [../application.md](../application.md) — behavior spec
- [01 reference-agent/go](../../../01-reference-agent/go/) — baseline without LaunchDarkly
