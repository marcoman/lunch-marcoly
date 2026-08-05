# Python (console)

Curses console version of the [01-reference-agent](../application.md) equity briefing demo.

Fixed **command chrome** at the top (single-letter hotkeys); **scrollable output** below. Domain logic is shared with the [Python web app](../python/) (`agent_core`, `yahoo_news`, shared system prompt).

## Prerequisites

- Python **3.12+**
- Repository virtual environment at the repo root (same as other Python examples)
- A terminal that supports **curses** (macOS Terminal, iTerm, Linux, Windows Terminal via WSL)
- Optional: [Ollama](https://ollama.com) or AWS Bedrock (same env vars as the web app)

From the **repository root**:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

OS setup (macOS / Linux / Windows / WSL): see [../python/README.md](../python/README.md).

## Environment variables

Same as the web app:

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_LLM_MODE` | auto / `stub` | `stub` \| `ollama` \| `bedrock`. If unset, auto-selects `ollama` when the daemon responds |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Local Ollama base URL |
| `OLLAMA_MODEL` | `llama3.2:3b` | Ollama model tag |
| `AWS_PROFILE` | `Administrator` | Bedrock SSO profile |
| `AWS_REGION` | `us-east-1` | Bedrock region |
| `AGENT_CONSOLE_THEME` | `default` | Color palette: `default` or `high-contrast` |

## Run

From this directory, with `.venv` active:

```bash
python 01-reference-agent.py
```

### Stub

Force stub even if Ollama is running:

```bash
AGENT_LLM_MODE=stub python 01-reference-agent.py
```

### Ollama

With Ollama running and `llama3.2:3b` pulled, the console **auto-selects ollama** when `AGENT_LLM_MODE` is unset. You can also force it:

```bash
ollama pull llama3.2:3b
AGENT_LLM_MODE=ollama python 01-reference-agent.py
```

Press `(m)ode` in the UI to cycle `stub` → `ollama` → `bedrock`.

## Screen chrome

```text
01-reference-agent[python-console]              Tickers: NVDA (2 stories) SPCX (2 stories)
AGENT_LLM_MODE=stub  model=default-no-llm                         Name: Conservative Charlie.
(t)ickers  st(o)ries  (s)tatus  (g)enerate report  (m)ode  (q)uit                              (n)ext user
```

| Row | Left (operational) | Right (personalization) |
|-----|--------------------|-------------------------|
| 0 | App banner | Tickers + per-ticker story counts |
| 1 | `AGENT_LLM_MODE` + `model` | User name |
| 2 | Workflow commands + mode + quit | Next user |

Successful Yahoo fetches are persisted in [`../stories/stories_cache.json`](../stories/stories_cache.json) (shared by all languages). The console restores the last cached pair on startup when available.

| Key | Action |
|-----|--------|
| `t` | Prompt for two tickers (footer) |
| `o` | Fetch Yahoo headlines (no LLM) |
| `s` | Status snapshot in the output pane |
| `g` | Stream AI report from loaded stories |
| `m` | Cycle LLM mode (`stub` → `ollama` → `bedrock`) |
| `q` | Quit |
| `n` | Next user (wrap; no LLM) |
| `↑` `↓` `PgUp` `PgDn` | Scroll output |

Typical session: `o` (stories) → `g` (generate with Ollama) → `q`.

## What to expect

1. Banner shows `01-reference-agent[python-console]` with tickers/story counts on the right; mode/model and user name on the second line.
2. Menu hotkeys are **bold cyan**; the user name is **bold yellow**; the footer tints green/yellow/red/cyan by status.
3. Output pane: ticker 1 / its stories in **green**, ticker 2 / its stories in **magenta**; **Prompt** is blue, **Response** is cyan.
4. Optional theme: `AGENT_CONSOLE_THEME=high-contrast` (or `default`). Curses has no stock themes — these are app palettes; your terminal theme still affects the base colors.
5. Command keys stay visible at the top; long reports scroll in the middle pane.
6. Footer shows status (“Fetching…”, errors, “Done…”).
7. Switching users never calls the LLM.

## Related

- [Parent README](../README.md)
- [application.md](../application.md) — behavior spec (web panels vs console chrome)
- [python/README.md](../python/README.md) — web twin
