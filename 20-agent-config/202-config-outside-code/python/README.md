# 202-config-outside-code — Python web

Port **8220**. Requires repo venv + `LD_SDK_KEY`.

```bash
source ../../../.venv/bin/activate
export LD_SDK_KEY=sdk-...
# Best Betty:
export ANTHROPIC_API_KEY=sk-ant-...
python 202-config-outside-code.py
```

Open http://127.0.0.1:8220/

| File | Role |
|------|------|
| `202-config-outside-code.py` | HTTP + SSE + `/api/feedback` |
| `agent_core.py` | **LD insertion:** `completion_config` · `track_metrics_of` · `track_feedback` |
| `yahoo_news.py` | Headlines (same as 01/21) |
| `index.html` | UI + thumbs + **Trace** dock (under Prompt/Response) |

After Generate, open **LaunchDarkly → Received** for the served variation, evaluation reason, resumption token, and the metrics `track_metrics_of` recorded. **Trace** under Prompt/Response is the step log. Thumbs 👍/👎 append a **feedback** line with Monitoring `eventKey`, variation, and short `runId`.

Provision the config first: [`../rest/create-config.sh`](../rest/create-config.sh) then [`../update-name-targeting.sh`](../rest/update-name-targeting.sh).
