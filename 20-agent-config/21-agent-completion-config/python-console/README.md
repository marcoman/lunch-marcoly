# Python console — AgentControl completion config

Curses console twin of the [Python web app](../python/). Same LaunchDarkly **AgentControl** generate path (`completion_config` → model + system/user messages); fixed hotkey chrome instead of a browser.

Keywords: **AgentControl** · **completion config** · **AI SDK** · **message variables** (`{{ stories }}`)

| Topic | Docs |
|-------|------|
| Python AI SDK | [Python AI SDK reference](https://launchdarkly.com/docs/sdk/ai/python) |
| Customize configs | [Customizing AgentControl configs](https://launchdarkly.com/docs/sdk/features/agentcontrol-config) |
| Provision this config | [../rest/README.md](../rest/README.md) |

## Prerequisites

Same as the web app:

1. Repo `.venv` + `pip install -r requirements.txt`
2. Provisioned config: `cd ../rest && ./create-config.sh`
3. `LD_SDK_KEY` for the targeted environment
4. Ollama with the three demo tags (see [../rest/README.md](../rest/README.md))
5. A terminal that supports **curses**

```bash
export LD_SDK_KEY="sdk-..."
# optional: export LD_AGENT_CONFIG_KEY="equity-briefing-completion"
ollama pull llama3.2:3b    # Charlie — best
ollama pull gemma2:2b      # Nancy / Amelia — default
ollama pull llama3.2:1b    # Toby — simple
```

## Run

From the **repository root**:

```bash
source .venv/bin/activate
cd 20-agent-config/21-agent-completion-config/python-console
python 21-agent-completion-config.py
```

## Screen chrome

```text
21-agent-completion-config[python-console]     Tickers: NVDA (2 stories) SPCX (2 stories)
ollama / llama3.2:3b                           Name: Conservative Charlie.
(t)ickers  st(o)ries  (s)tatus  (l)d  (c)lear  (g)enerate report  (q)uit     (n)ext user
```

Before the first generate, the middle row shows `config:equity-briefing-completion`. After generate, it shows the **served** provider/model.

| Key | Action |
|-----|--------|
| `t` | Set two tickers |
| `o` | Fetch Yahoo headlines (shared `../stories/` cache) |
| `s` | Status: user, tickers, stories + one-line last LD variation |
| `l` | Last LD **sent** / **received** (context, variation, message previews, pretty reason JSON) |
| `c` | Clear the output pane (keeps persona, stories, last LD tx) |
| `g` | Generate — LD evaluate → stream report |
| `n` | Next persona (wrap; no LLM until `g`) |
| `q` | Quit |
| `↑` `↓` `PgUp` `PgDn` | Scroll output |

Typical session: `o` → `g` → `l` → `c` → `n` → `g` (compare variations) → `q`.

## What to expect

1. **Generate** prints `LD: <variationKey>  provider / model`, then **System** / **Prompt** as first-line previews (~80 chars)—not the full message bodies.
2. **Response** streams below (cyan).
3. Press **`l`** for the last evaluation: context, `stories` preview, variation, truncated messages, and indented **reason JSON**.
4. **`c`** clears scrollback for a clean pane; session state stays.
5. **`s`** stays lean: ops snapshot + one `Last LD: variation=…` line.
6. Switch users: **Charlie** → `concise-skeptic`; **Nancy** → `baseline-analyst`; **Toby** → `reckless-hype`; **Anonymous Amelia** → fallthrough `baseline-analyst`.

Optional theme: `AGENT_CONSOLE_THEME=high-contrast` (or `default`).

## Architecture

| File | Role |
|------|------|
| `21-agent-completion-config.py` | Curses UI |
| [`../python/agent_core.py`](../python/agent_core.py) | **LD insertion:** `completion_config` → stream |
| [`../python/yahoo_news.py`](../python/yahoo_news.py) | Yahoo + shared stories cache |

No `(m)ode` cycle here — the served AgentControl variation owns provider/model (unlike [01 python-console](../../../01-reference-agent/python-console/)).

## Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |
| `LD_AGENT_CONFIG_KEY` | No | Default `equity-briefing-completion` |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | For Custom/Ollama variations | Defaults match web |
| `AWS_PROFILE` / `AWS_REGION` | For Bedrock models | Only if the variation names Bedrock |
| `AGENT_CONSOLE_THEME` | No | `default` or `high-contrast` |

## Related

- [../python/README.md](../python/README.md) — web twin
- [../README.md](../README.md) — example landing
- [../application.md](../application.md) — behavior spec
- [01 python-console](../../../01-reference-agent/python-console/) — baseline without LaunchDarkly
