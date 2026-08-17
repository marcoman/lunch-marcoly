# 22-config-outside-code — Python web

Port **8220**. Requires repo venv + `LD_SDK_KEY`.

```bash
source ../../../.venv/bin/activate
export LD_SDK_KEY=sdk-...
# Best Betty:
export ANTHROPIC_API_KEY=sk-ant-...
python 22-config-outside-code.py
```

Open http://127.0.0.1:8220/

| File | Role |
|------|------|
| `22-config-outside-code.py` | HTTP + SSE + `/api/feedback` |
| `agent_core.py` | **LD insertion:** `completion_config` · `track_metrics_of` · `track_feedback` |
| `yahoo_news.py` | Headlines (same as 01/21) |
| `index.html` | UI + thumbs |

Provision the config first: [`../rest/create-config.sh`](../rest/create-config.sh) then [`../update-name-targeting.sh`](../rest/update-name-targeting.sh).
