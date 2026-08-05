# Java (console)

Terminal UI version of the [01-reference-agent](../application.md), matching the [Python console](../python-console/) chrome and hotkeys.

Reuses `AgentCore` / `YahooNews` from [`../java/`](../java/) via Maven `build-helper` (same domain logic as the web app).

## Prerequisites

- Java **21+**
- Maven Wrapper in this folder (`./mvnw`)
- Interactive TTY (`stty` raw mode; macOS / Linux / WSL)
- Optional: [Ollama](https://ollama.com)

## Build

```bash
cd 01-reference-agent/java-console
./mvnw clean package
```

## Run

Run from **this directory** so `../prompts/system_prompt.txt` resolves:

```bash
java -jar target/01-reference-agent-console.jar
```

If Ollama is reachable and `AGENT_LLM_MODE` is unset, mode defaults to **ollama**.

```bash
AGENT_LLM_MODE=stub java -jar target/01-reference-agent-console.jar
AGENT_LLM_MODE=ollama java -jar target/01-reference-agent-console.jar
```

Terminal size is read from the TTY (`stty size`). Exported `COLUMNS` / `LINES`
override that if set. Note: shell `$COLUMNS` is often not exported — use
`printenv COLUMNS` to check, or:

```bash
COLUMNS=120 LINES=40 java -jar target/01-reference-agent-console.jar
```

## Screen chrome

```text
01-reference-agent[java-console]              Tickers: NVDA (2 stories) SPCX (2 stories)
AGENT_LLM_MODE=ollama  model=llama3.2:3b                         Name: Conservative Charlie.
(t)ickers  st(o)ries  (s)tatus  (g)enerate report  (m)ode  (q)uit                    (n)ext user
```

| Key | Action |
|-----|--------|
| `t` | Set tickers |
| `o` | Fetch Yahoo stories |
| `s` | Status |
| `g` | Generate AI report |
| `m` | Cycle LLM mode (`stub` → `ollama` → `bedrock`) |
| `q` | Quit |
| `n` | Next user |
| arrows / PgUp / PgDn | Scroll output |

## Related

- [python-console/README.md](../python-console/README.md) — reference TUI behavior
- [java/README.md](../java/README.md) — web twin
