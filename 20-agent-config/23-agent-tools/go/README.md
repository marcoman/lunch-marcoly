# Go (console)

Terminal UI twin of the web ports (Python/Node/Java/.NET), matching the
[21-agent-completion-config Go console](../../21-agent-completion-config/go/)
chrome and hotkeys. Same completion config as 21, plus **Library tools**:
the model must call `analyze-ticker-stories` once per ticker, then
`compare-ticker-analyses`, before writing the briefing — grounded in headline
evidence instead of invented claims.

Keywords: **AgentControl** · **Library tools** · **CompletionConfig.Tools()** ·
**tool loop** · **TrackToolCall** · **TrackMetricsOf**

| Topic | Docs |
|-------|------|
| Tools | [AgentControl Library tools](https://launchdarkly.com/docs/home/agentcontrol/tools) |
| Go AI SDK | [Go AI SDK reference](https://launchdarkly.com/docs/sdk/ai/go) |
| AI metrics | [Tracking AI metrics](https://launchdarkly.com/docs/sdk/features/ai-metrics) |
| Provision this config | [../rest/README.md](../rest/README.md) |

## Prerequisites

- Go **1.24+**
- Interactive TTY
- Provisioned config + tools: `cd ../rest && ./create-config.sh && ./create-tools.sh`
  (or whichever script your `rest/` layout uses to attach both tools)
- `LD_SDK_KEY` for the targeted environment
- `ANTHROPIC_API_KEY` for **Analyst Claude**
- `ollama pull llama3.2:3b` for **Analyst Llama**, `ollama pull llama3.2:1b` for **Analyst Gwen**

```bash
export LD_SDK_KEY="sdk-..."
# optional: export LD_AGENT_CONFIG_KEY="equity-briefing-tools"
export ANTHROPIC_API_KEY="sk-ant-..."   # Analyst Claude
ollama pull llama3.2:3b                 # Analyst Llama
ollama pull llama3.2:1b                 # Analyst Gwen
ollama list
```

## Build

From this directory:

```bash
go mod tidy
go build -o 23-agent-tools .
```

## Run

Run from **this directory** so `../rest/messages/` (baseline fallback prompts)
and `../stories/` (shared Yahoo cache) resolve:

```bash
./23-agent-tools
```

Unlike [21-agent-completion-config/go](../../21-agent-completion-config/go/),
there is **no model-only fallback** here: Library tools only exist on a live
AgentControl config, so a missing `LD_SDK_KEY`, an unreachable LaunchDarkly, or
a disabled/untooled config is a hard stop (an `error` line telling you to run
`rest/create-tools.sh` / `rest/create-config.sh`) instead of a silent baseline
generation.

## Screen chrome

```text
23-agent-tools[go]                            Tickers: NVDA (2 stories) SPCX (2 stories)
config:equity-briefing-tools                             Name: Analyst Claude.
(t)ickers  st(o)ries  (s)tatus  (g)enerate  (q)uit                (n)ext user
```

Before the first generate, the middle row shows `config:equity-briefing-tools`.
After generate, it shows the **served** provider/model (e.g. `anthropic / claude-sonnet-5`
or `ollama / llama3.2:3b`).

| Key | Action |
|-----|--------|
| `t` | Set two tickers |
| `o` | Fetch Yahoo headlines (shared `../stories/` cache) |
| `s` | Status: user, tickers, config key, served provider/model, attached tools, last tool-call trace, stories |
| `g` | Generate — LD evaluate → tool loop → stream report |
| `n` | Next persona (wrap; no LLM call until `g`) |
| `q` | Quit |
| `↑` `↓` `PgUp` `PgDn` | Scroll output |

No `(m)ode` hotkey — the served AgentControl variation owns provider + model
for Claude; Ollama persona/tag is a local UI choice (see below).

Typical session: `o` → `g` → `s` → `n` → `g` (compare personas) → `q`.

## Tool trace

Every dispatched tool call prints as it runs — no separate panel needed:

```text
Tool #1: analyze-ticker-stories (round 1)
  args:   {"stories":[...],"ticker":"NVDA"}
  result: {"claims":[...],"summary":"NVDA: net positive headline tone (2 stories).","ticker":"NVDA","tone_score":2}
Tool #2: analyze-ticker-stories (round 2)
  ...
Tool #3: compare-ticker-analyses (round 3)
  ...
```

`(s)tatus` also summarizes the last run, e.g.
`Last run: 3 tool call(s) — analyze-ticker-stories → analyze-ticker-stories → compare-ticker-analyses`.

## Personas (local, not LD name targeting)

| Persona | Runtime | Model | Notes |
|---------|---------|-------|-------|
| Analyst Claude | Anthropic | LD-served model (`claude-sonnet-5` default) | Cleanest tool-calling; best demo |
| Analyst Llama | Ollama | `llama3.2:3b` (pinned) | Local; guardrails below usually get it through the full loop |
| Analyst Gwen | Ollama | `llama3.2:1b` (pinned) | Smallest/flakiest — expect more skipped tools, more guardrail rescues |

Every persona evaluates the **same** `equity-briefing-tools` variation and
tool schemas. Provider/model routing per persona is a **local app** choice
(`persona.Profile` / `persona.Model` in `agent.go`), not LaunchDarkly targeting —
mirrors the Python/Node source of truth.

## Ollama guardrails (ported from `python/agent_core.py`)

Small local models are unreliable tool callers. `runOllamaToolLoop` in
`agent.go` ports the same rescues as the Python/Node/.NET twins:

1. **Suffix** — every Ollama system prompt gets `ollamaToolSuffix` appended: call tools first, one at a time, don't invent `analysis_a`/`analysis_b` fields.
2. **Nudge** — if the model skips tools entirely on turn 1, inject one user message telling it to stop writing and call tools now.
3. **Sort** — if a turn returns multiple tool calls, run `analyze-ticker-stories` calls before `compare-ticker-analyses` in that turn.
4. **Compare rewrite** — if `compare-ticker-analyses` args don't look like real analyze output (`normalizeCompareArgs`), silently substitute the two most recent real analyze results.
5. **Force compare** — if the model analyzed both tickers but never called compare, run `compare-ticker-analyses` once from those results and ask for a final briefing grounded in it.

Claude (Anthropic) does not need any of this — `runAnthropicToolLoop` is a
plain tool_use loop.

## What to expect

1. **Generate** prints `LD: config=… fallback=…`, `Provider: … / …`, `Tools attached: …`, the **Prompt** (user message, `{{ stories }}` substituted), then the **tool trace** as each call runs, then streams the **Response** (cyan).
2. **Analyst Claude** → Anthropic tool_use loop. **Analyst Llama** → Ollama `llama3.2:3b` with guardrails. **Analyst Gwen** → Ollama `llama3.2:1b`, same guardrails, more likely to need the nudge/rewrite/force-compare rescues.
3. **`s`** shows attached tool schemas and the tool-call sequence from the last generate, alongside the ops snapshot.
4. **Metrics** line includes `tool_calls=N` alongside latency/tokens/finish-reason.

## Architecture

| File | Role |
|------|------|
| `main.go` | Raw-terminal TUI (chrome, hotkeys, scrollback, **tool trace rendering**) — adapted from [21-agent-completion-config/go/main.go](../../21-agent-completion-config/go/main.go) |
| `agent.go` | **LD insertion:** `aiClient.CompletionConfig(...)` → `config.Tools()` → tool loop → `tracker.TrackToolCall(name)` / `ldai.TrackMetricsOf(...)`. See the file header for the full read-order. |
| `yahoo.go` | Yahoo headlines + shared `../stories/` cache — unchanged from [21-agent-completion-config/go/yahoo.go](../../21-agent-completion-config/go/yahoo.go) |

## `TrackToolCall` API (Go)

```go
tracker := config.CreateTracker()           // ldai.Tracker, from AICompletionConfig
err := tracker.TrackToolCall(toolName)      // one call per dispatched tool
```

Signature: `func (t *ldai.Tracker) TrackToolCall(toolKey string) error` —
called once immediately after each `dispatchTool(...)` in both
`runAnthropicToolLoop` and `runOllamaToolLoop` (including the force-compare
guardrail path), so the config's **Monitoring** tab reflects every tool
execution, not just ones the model reasons through cleanly.

LLM request metrics use the sibling, mode-agnostic
`ldai.TrackMetricsOf[T any](tracker *Tracker, extract func(T) ldai.AIMetrics, operation func() (T, error)) (T, error)`
wrapping each `anthropicChat` / `ollamaChat` call — this repo intentionally
prefers it over the deprecated `TrackRequest` API.

## Go AI SDK note (API quirks vs Python / Node / .NET)

Same caveat as [21-agent-completion-config/go](../../21-agent-completion-config/go/#go-ai-sdk-note-api-quirks-vs-python--node--net):
this example imports `github.com/launchdarkly/go-server-sdk-ai` (aliased `ld`
in `agent.go`) for `CompletionConfig`, `ToolConfig`, `Tracker.TrackToolCall`,
and `ldai.TrackMetricsOf` — the bundled `go-server-sdk/ldai` package has none
of these.

- **`config.Tools()`** returns `map[string]ld.ToolConfig` (promoted from the
  embedded `aiConfigBase`). Each `ToolConfig` exposes `Name()`,
  `Description()`, and `Parameters() map[string]ldvalue.Value` — converted to
  plain JSON via `ldvalue.Value.AsArbitraryValue()` (see `toolParameters` in
  `agent.go`), then reshaped into Anthropic's `input_schema` and
  OpenAI/Ollama's `function.parameters` shapes.
- **No explicit network-failure branch** for the completion call itself —
  `CompletionConfig()` never errors; a bad key or unreachable LD silently
  returns the supplied default. This example folds that into the same
  `usingFallback` check as 21 (`!config.Enabled() || config.VariationKey() == ""`),
  but here it's a **hard stop** with provisioning guidance rather than a code
  baseline, because tools don't exist off-LaunchDarkly.
- Tool call arguments arrive differently per provider: Anthropic gives typed
  JSON objects directly (`block["input"]`); Ollama's `/api/chat` can return
  `function.arguments` as either an object or a JSON-encoded string —
  `toolCallArguments()` normalizes both.

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key; no fallback path for tools |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-tools` |
| `ANTHROPIC_API_KEY` | For Analyst Claude | Anthropic Messages API |
| `ANTHROPIC_MODEL` | No | Overrides the LD-served model name if it isn't a `claude*` id |
| `OLLAMA_HOST` | No | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | No | Fallback tag if a persona's pinned `Model` is empty |

## Related

- [../README.md](../README.md) — example landing (tool architecture diagram, LD keys, all-language quick start)
- [../application.md](../application.md) — behavior spec
- [21-agent-completion-config/go](../../21-agent-completion-config/go/) — completion-only console this builds on
- [../python/agent_core.py](../python/agent_core.py) · [../node/agentCore.js](../node/agentCore.js) — source-of-truth tool loop this port mirrors
