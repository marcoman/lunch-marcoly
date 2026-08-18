# Go (console)

Terminal UI version of the [01-reference-agent](../application.md), matching the [Python console](../python-console/) chrome and hotkeys.

## Prerequisites

- Go **1.22+**
- Interactive TTY
- Optional: [Ollama](https://ollama.com)

## Build

From this directory:

```bash
go mod tidy
go build -o 01-reference-agent .
```

## Run

Run from **this directory** so `../prompts/system_prompt.txt` and `../stories/` resolve:

```bash
./01-reference-agent
```

If Ollama is reachable and `AGENT_LLM_MODE` is unset, mode defaults to **ollama**.

```bash
AGENT_LLM_MODE=stub ./01-reference-agent
AGENT_LLM_MODE=ollama ./01-reference-agent
```

## Screen chrome

```text
01-reference-agent[go]                        Tickers: NVDA (2 stories) SPCX (2 stories)
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
- [node-console/README.md](../node-console/README.md) — Node twin
- [java-console/README.md](../java-console/README.md) — Java twin
