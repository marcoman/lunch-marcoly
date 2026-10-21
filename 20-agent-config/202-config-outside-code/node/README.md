# 22-config-outside-code — Node web

Port **8221**. Requires Node 20+, `LD_SDK_KEY`, and (for Best Betty) `ANTHROPIC_API_KEY`.

```bash
nvm use   # repo root .nvmrc
npm install
export LD_SDK_KEY=sdk-...
export ANTHROPIC_API_KEY=sk-ant-...   # Best Betty
npm start
```

Open http://127.0.0.1:8221/

| File | Role |
|------|------|
| `22-config-outside-code.js` | HTTP + SSE + `/api/feedback` |
| `agentCore.js` | **LD insertion:** `completionConfig` · `trackMetricsOf` · `trackFeedback` |
| `yahooNews.js` | Headlines |
| `index.html` | UI + thumbs |

Provision: [`../rest/create-config.sh`](../rest/create-config.sh).
