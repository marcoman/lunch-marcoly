# C++ (console)

Terminal UI version of the [01-reference-agent](../application.md), matching the [Python console](../python-console/) chrome and hotkeys.

## Prerequisites

- C++20-capable compiler (`c++` / clang++ / g++)
- Make
- [libcurl](https://curl.se/libcurl/) (macOS / Linux; Homebrew: `brew install curl`)
- `curl` CLI (first build downloads [nlohmann/json](https://github.com/nlohmann/json) into `third_party/`)
- Interactive TTY
- Optional: [Ollama](https://ollama.com)

## Build

From this directory:

```bash
make clean
make all
```

## Run

Run from **this directory** so `../prompts/` and `../stories/` resolve:

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
01-reference-agent[cpp]                       Tickers: NVDA (2 stories) SPCX (2 stories)
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
- [rust/README.md](../rust/README.md) — Rust twin
