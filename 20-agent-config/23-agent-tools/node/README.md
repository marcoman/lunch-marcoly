# 23-agent-tools — Node web

Port **8231**. Requires Node 20+, `LD_SDK_KEY`, and a provisioned AgentControl config
(`equity-briefing-tools` with Library tools attached).

- **Analyst Claude** → `ANTHROPIC_API_KEY`
- **Analyst Llama** → Ollama `llama3.2:3b` (`ollama pull llama3.2:3b`)
- **Analyst Gwen** → Ollama `llama3.2:1b` (smaller; more skips)

```bash
cd 20-agent-config/23-agent-tools/node
npm install
export LD_SDK_KEY=sdk-...
export ANTHROPIC_API_KEY=sk-ant-...   # Claude
npm start
# Open http://127.0.0.1:8231/
```

| File | Role |
|------|------|
| `23-agent-tools.js` | HTTP + SSE |
| `agentCore.js` | **LD insertion:** `completionConfig` · tool loop · `trackToolCall` |
| `yahooNews.js` | Headlines → `../stories/` |
| `index.html` | UI + tool trace |

Provision first: [`../rest/create-config.sh`](../rest/create-config.sh).  
Parent: [../README.md](../README.md)
