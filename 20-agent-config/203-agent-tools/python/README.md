# 23-agent-tools — Python web

Port **8230**. Requires repo venv + `LD_SDK_KEY`.

- **Analyst Claude** → `ANTHROPIC_API_KEY`
- **Analyst Llama** → Ollama `llama3.2:3b` (`ollama pull llama3.2:3b`)
- **Analyst Gwen** → Ollama `llama3.2:1b` (smaller; more skips)

Local Ollama personas share the tool-loop hardenings (nudge, compare-arg rewrite,
compare guardrail). Prefer Claude for a clean model-driven tools demo.

```bash
source ../../../.venv/bin/activate
export LD_SDK_KEY=sdk-...
export ANTHROPIC_API_KEY=sk-ant-...   # Claude
python 23-agent-tools.py
```

Open http://127.0.0.1:8230/

| File | Role |
|------|------|
| `23-agent-tools.py` | HTTP + SSE |
| `agent_core.py` | **LD insertion:** `completion_config` · tool loop · `track_tool_call` |
| `yahoo_news.py` | Headlines |
| `index.html` | UI + tool trace panel + **Trace** dock (under Prompt/Response) |

After Generate, the dedicated **Tool trace** panel shows rich tool I/O; the **Trace** dock is the compact under-the-hood log (prompt → model → tools → draft → metrics).

Provision first: [`../rest/create-config.sh`](../rest/create-config.sh).
