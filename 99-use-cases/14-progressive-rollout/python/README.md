# Python (web)

Web grid navigator for [04-progressive-rollout](../application.md).

Shared evaluation lives in [`../highlight_eval.py`](../highlight_eval.py).

## Run

```bash
python 04-progressive-rollout.py
```

Open http://localhost:8080/. Toggle the flag in LaunchDarkly — the page polls every 500 ms.

```bash
python 04-progressive-rollout.py --evaluate-once alice
```
