# Go (console)

Terminal UI twin of the web ports (Python/Node/Java/.NET). **No HTTP port** — fixed
hotkey chrome like [21-agent-completion-config/go](../../21-agent-completion-config/go/).
Same runtime gate: draft → two custom judges (≥ **0.65** AND) → optional one
**Conservative Charlie** rewrite.

Keywords: **AgentControl** · **Judges** · **JudgeConfig** · **TrackJudgeResponse** ·
**runtime gate** · **Ollama JSON**

| Topic | Docs |
|-------|------|
| Judges | [Judges](https://launchdarkly.com/docs/home/agentcontrol/judges) |
| Go AI SDK | [Go AI SDK reference](https://launchdarkly.com/docs/sdk/ai/go) |
| AI metrics | [Tracking AI metrics](https://launchdarkly.com/docs/sdk/features/ai-metrics) |
| Spec | [../application.md](../application.md) |

## Prerequisites

- Go **1.24+**
- Interactive TTY
- `LD_SDK_KEY` for the targeted environment
- Provisioned configs:

```bash
export LD_SDK_KEY="sdk-..."
ollama pull llama3.2:1b    # Toby draft
ollama pull llama3.2:3b    # Judges
ollama pull llama3.1:8b    # Charlie rewrite

cd ../rest
./create-judges.sh
./create-config.sh
```

## Build & run

From this directory (so `../rest/messages/` and `../stories/` resolve):

```bash
cd 20-agent-config/24-agent-judges/go
go mod tidy
go run .
# or: go build -o 24-agent-judges . && ./24-agent-judges
```

## Screen chrome

```text
24-agent-judges[go]                           Tickers: NVDA (2 stories) SPCX (2 stories)
config:equity-briefing-judged                            Name: Thoughtless Toby.
(t)oby  (c)harlie  storie(s)  tic(k)ers  (g)enerate  (q)uit      1=Toby  2=Charlie
```

| Key | Action |
|-----|--------|
| `t` / `1` | Thoughtless Toby |
| `c` / `2` | Conservative Charlie |
| `s` (`o` alias) | Fetch Yahoo headlines (`../stories/` cache) |
| `k` | Set two tickers |
| `g` | Generate — draft → judges → optional Charlie rewrite |
| `q` | Quit |
| `↑` `↓` `PgUp` `PgDn` | Scroll output |

## Demo

1. Press **`t`** (Thoughtless Toby).
2. Press **`s`** (Get Stories).
3. Press **`g`** (Generate).
4. Expect: **Draft** → failing **Judge scores** → **Rewrite (Conservative Charlie)**.

Optional control: **`c`** then **`g`** — Charlie alone usually passes without a rewrite.

## JudgeConfig note (Go AI SDK)

Completion uses `CompletionConfig` (same as 21). Judges use
`client.JudgeConfig(...)` for prompts/model/metric key from LaunchDarkly, then
**Ollama `/api/chat` with `format: "json"`** for `{score, reasoning}`.

Scores are reported with **`tracker.TrackJudgeResponse(datamodel.JudgeResponse{...})`**
(metric keys like `$ld:ai:judge:source-fidelity`). Pass threshold: both judges
≥ **0.65** (`JUDGE_PASS_THRESHOLD`).

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-judged` |
| `LD_JUDGE_FIDELITY_KEY` | No | Default `equity-briefing-source-fidelity` |
| `LD_JUDGE_DISCIPLINE_KEY` | No | Default `equity-briefing-recommendation-discipline` |
| `JUDGE_PASS_THRESHOLD` | No | Default `0.65` |
| `OLLAMA_HOST` | No | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | No | Default `llama3.2:3b` (SDK defaults / judges) |

Parent: [../README.md](../README.md) · Spec: [../application.md](../application.md)
