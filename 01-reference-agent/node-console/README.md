# Node.js (console)

Terminal UI version of the [01-reference-agent](../application.md), matching the [Python console](../python-console/) chrome and hotkeys.

Reuses [`../node/agentCore.js`](../node/agentCore.js) and [`../node/yahooNews.js`](../node/yahooNews.js) (no HTTP server).

## Prerequisites

- Node.js 20 LTS+ via [nvm](https://github.com/nvm-sh/nvm) (see root [`.nvmrc`](../../.nvmrc))
- Interactive TTY
- Optional: [Ollama](https://ollama.com)

```bash
nvm use
```

## Run

```bash
cd 01-reference-agent/node-console
npm start
# or: node 01-reference-agent.js
```

If Ollama is reachable and `AGENT_LLM_MODE` is unset, mode defaults to **ollama**.

```bash
AGENT_LLM_MODE=stub npm start
AGENT_LLM_MODE=ollama npm start
```

## Screen chrome

```text
01-reference-agent[node-console]              Tickers: NVDA (2 stories) SPCX (2 stories)
AGENT_LLM_MODE=ollama  model=llama3.2:3b                         Name: Conservative Charlie.
(t)ickers  st(o)ries  (s)tatus  (g)enerate report  (m)ode  (q)uit                    (n)ext user
```

| Key | Action |
|-----|--------|
| `t` | Set tickers |
| `o` | Fetch Yahoo stories |
| `s` | Status |
| `g` | Generate AI report |
| `m` | Cycle LLM mode (`stub` → `ollama` → `bedrock`; Bedrock generate is Python-only) |
| `q` | Quit |
| `n` | Next user |
| arrows / PgUp / PgDn | Scroll output |

## Related

- [python-console/README.md](../python-console/README.md) — reference TUI behavior
- [node/README.md](../node/README.md) — web twin
