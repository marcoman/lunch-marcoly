# Rust (console)

Terminal UI version of the [01-reference-agent](../application.md), matching the [Python console](../python-console/) chrome and hotkeys.

## Prerequisites

- Rust **1.75+** (2021 edition)
- Interactive TTY
- Optional: [Ollama](https://ollama.com)

## Build

From this directory:

```bash
cargo build --release
```

## Run

Paths to `../prompts/` and `../stories/` are resolved from this crate’s directory (`CARGO_MANIFEST_DIR`), so you can run the binary from here after a release build:

```bash
./target/release/01-reference-agent
```

If Ollama is reachable and `AGENT_LLM_MODE` is unset, mode defaults to **ollama**.

```bash
AGENT_LLM_MODE=stub ./target/release/01-reference-agent
AGENT_LLM_MODE=ollama ./target/release/01-reference-agent
```

## Screen chrome

```text
01-reference-agent[rust]                      Tickers: NVDA (2 stories) SPCX (2 stories)
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
- [go/README.md](../go/README.md) — Go twin
