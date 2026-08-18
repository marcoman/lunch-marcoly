# Go (console)

Terminal UI twin of the web ports, matching the [21-agent-completion-config Go console](../../21-agent-completion-config/go/) chrome and hotkeys. Same LaunchDarkly **AgentControl** completion config as 21 (`CompletionConfig` → model + system/user messages), but the teaching focus shifts to **tracked completion**: every generate wraps the LLM call in **`ldai.TrackMetricsOf`** so tokens / success / latency land on the config's **Monitoring** tab, and a **resumption token** lets two new hotkeys send thumbs feedback for that exact run.

Keywords: **AgentControl** · **completion config** · **AI metrics** · **`TrackMetricsOf`** · **resumption token** · **feedback**

| Topic | Docs |
|-------|------|
| AI metrics (`TrackMetricsOf`, feedback) | [Tracking AI metrics](https://launchdarkly.com/docs/sdk/features/ai-metrics) |
| Go AI SDK | [Go AI SDK reference](https://launchdarkly.com/docs/sdk/ai/go) |
| Config outside of code | [Managing AI model configuration outside of code](https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs) |
| Provision this config | [../rest/README.md](../rest/README.md) |

## Prerequisites

- Go **1.24+**
- Interactive TTY
- Provisioned config: `cd ../rest && ./create-config.sh && ./update-name-targeting.sh`
- `LD_SDK_KEY` for the targeted environment
- `ollama pull llama3.2:1b` — required for Anonymous Amelia / fallthrough (`tracked-ollama`)
- `ANTHROPIC_API_KEY` — required for Best Betty (`tracked-anthropic`); without it, Betty's generate errors (switch to Amelia with `n`, or export the key)

```bash
export LD_SDK_KEY="sdk-..."
# optional: export LD_AGENT_CONFIG_KEY="equity-briefing-tracked-completion"
export ANTHROPIC_API_KEY="sk-ant-..."   # Best Betty
ollama pull llama3.2:1b                 # Anonymous Amelia
```

## Build

From this directory:

```bash
go mod tidy
go build -o 22-config-outside-code .
```

## Run

Run from **this directory** so `../rest/messages/` (baseline fallback prompts) and `../stories/` (shared Yahoo cache) resolve:

```bash
./22-config-outside-code
```

Without `LD_SDK_KEY` (or if LaunchDarkly is unreachable, or the config is turned off), generate still works — it falls back to the in-code **baseline-analyst** prompts (`../rest/messages/baseline-*.txt`) against local Ollama. That path is **untracked**: no Monitoring events, no resumption token, and `+` / `-` report "no tracked report yet" until a real AgentControl-served generate succeeds.

## Screen chrome

```text
22-config-outside-code[go]                    Tickers: NVDA (2 stories) SPCX (2 stories)
config:equity-briefing-tracked-completion                            Name: Best Betty.
(t)ickers  st(o)ries  (s)tatus  (g)enerate  (+)up  (-)down  (q)uit          (n)ext user
```

Before the first generate, the middle row shows `config:equity-briefing-tracked-completion`. After generate, it shows the **served** provider/model (e.g. `anthropic / claude-sonnet-5`).

| Key | Action |
|-----|--------|
| `t` | Set two tickers |
| `o` | Fetch Yahoo headlines (shared `../stories/` cache) |
| `s` | Status: user, tickers, config key, served provider/model, last LD variation, feedback readiness |
| `g` | Generate — LD evaluate → `TrackMetricsOf` → stream report → mint resumption token |
| `+` | Thumbs **up** — `TrackFeedback(FeedbackPositive)` against the last tracked run |
| `-` | Thumbs **down** — `TrackFeedback(FeedbackNegative)` against the last tracked run |
| `n` | Next persona (wrap; no LLM call until `g`) |
| `q` | Quit |
| `↑` `↓` `PgUp` `PgDn` | Scroll output |

`+` / `-` always replay against the **persona and run that produced the resumption token**, even if you've since pressed `n` — the token is a self-contained, base64-encoded run id, so feedback lands on the correct Monitoring run regardless of what's on screen now. Pressing either before a tracked generate has completed shows "no tracked report yet" in the footer instead of sending anything.

Typical session: `o` → `g` → `+` (or `-`) → `s` → `n` → `g` (Anonymous Amelia) → `+` → `q`.

## What to expect

1. **Generate** prints `LD: <variationKey> config=<key>`, then `Provider: <provider> / <model>`, the full **Prompt** (the AgentControl **user** message, `{{ stories }}` already substituted), then streams the **Response** (cyan) in fixed-size chunks — the provider calls are non-streaming so `TrackMetricsOf`'s extractor can inspect the whole typed result, same as the Python/Node/.NET ports.
2. On `done`, a `Tracked: press + (up) or - (down)…` line appears (green) — that's your cue the run minted a resumption token. `s` also flags this: `Feedback: ready for <persona> — press + or -`.
3. Switch personas with `n`: **Best Betty** → `tracked-anthropic` (`claude-sonnet-5`, requires `ANTHROPIC_API_KEY`) · **Anonymous Amelia** → fallthrough `tracked-ollama` (`llama3.2:1b`, anonymous context — no name targeting can match).
4. After a few `+`/`-` presses, check `../rest/get-feedback-status.sh --verbose` for thumbs counts/rates and Monitoring links (allow ~1 min for aggregation).

## Architecture

| File | Role |
|------|------|
| `main.go` | Raw-terminal TUI (chrome, hotkeys incl. `+`/`-`, scrollback) — adapted from [21-agent-completion-config/go/main.go](../../21-agent-completion-config/go/main.go) |
| `agent.go` | **LD insertion:** `aiClient.CompletionConfig(...)` → `config.CreateTracker()` → `ldai.TrackMetricsOf(...)` for generate; `aiClient.CreateTracker(token, ctx)` → `tracker.TrackFeedback(...)` for thumbs. See the file header for the full read-order. |
| `yahoo.go` | Yahoo headlines + shared `../stories/` cache — unchanged from [21-agent-completion-config/go/yahoo.go](../../21-agent-completion-config/go/yahoo.go) / [01-reference-agent/go/yahoo.go](../../../01-reference-agent/go/yahoo.go) |

## Go AI SDK note (API quirks vs Python / Node / .NET)

Builds on the module-path quirk documented in [21/go/README.md](../../21-agent-completion-config/go/README.md#go-ai-sdk-note-api-quirks-vs-python--node--net) (this example imports the same separate `github.com/launchdarkly/go-server-sdk-ai` module, package `ldai`, aliased `ld` here). Additional quirks specific to **tracked completion**:

- **`TrackMetricsOf` is a free generic function, not a `Tracker` method.** Go methods can't declare their own type parameters, so the SDK exposes `ldai.TrackMetricsOf[T any](t *Tracker, extract func(T) AIMetrics, operation func() (T, error)) (T, error)` at package scope instead of `tracker.TrackMetricsOf(...)`. Python/Node/.NET all attach the equivalent (`track_metrics_of` / `trackMetricsOf` / `TrackMetricsOf`) directly as a method on the tracker object — call-site shape differs, behavior doesn't.
- **`Tracker.ResumptionToken()` is synchronous and local** — it base64-encodes `{runId, configKey, variationKey, version}`; minting one costs no network round trip. `aiClient.CreateTracker(token, ctx)` decodes it back into a `*Tracker` that reuses the original `runId`, so feedback events correlate with the generate that produced them in Monitoring. Same contract as the other AI SDKs' `createTracker(token, context)` / `create_tracker(token, context)`.
- **`TrackRequest` still exists but is deprecated** in favor of `TrackMetricsOf` — this example uses `TrackMetricsOf` throughout, matching the task's guidance to prefer it.
- **Feedback is a typed enum**, `ld.FeedbackPositive` / `ld.FeedbackNegative` (type `ld.Feedback`), passed to `tracker.TrackFeedback(...)` — not a free-form string like the REST event keys (`$ld:ai:feedback:user:positive` / `...negative`) shown in `../rest/get-feedback-status.sh`.
- **Non-streaming provider calls.** Like the Python/Node/.NET ports (and unlike 21's Go port, which streams Ollama), this example calls Ollama with `stream:false` and Anthropic's non-streaming Messages API, because `TrackMetricsOf`'s `extract` function needs one typed result (`genResult{Text, PromptTokens, CompletionTokens}`) to compute token metrics. Tokens are then chunked to the UI in fixed 24-rune pieces for the same "streaming" feel.
- **No official Anthropic Go SDK used** — like Node/Python/.NET, this example calls the Anthropic Messages API directly over `net/http` (see `anthropicComplete` in `agent.go`).

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes (else falls back to code baseline, untracked) | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-tracked-completion` |
| `ANTHROPIC_API_KEY` | For Best Betty (`tracked-anthropic`) | Claude API key |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | For Ollama variations | `OLLAMA_MODEL` only backs the code-baseline fallback; served variations carry their own model |

## Related

- [../README.md](../README.md) — example landing (architecture diagram, ports, `get-feedback-status.sh`)
- [../rest/README.md](../rest/README.md) — provisioning + feedback status script
- [21-agent-completion-config/go](../../21-agent-completion-config/go/) — completion config without tracking (baseline for this port's chrome)
- [../python/README.md](../python/README.md) · [../node/README.md](../node/README.md) · [../java/README.md](../java/README.md) · [../dotnet/README.md](../dotnet/README.md) — web twins
