# Python (web)

Web grid navigator for [15-guarded-rollout](../application.md).

Shared evaluation lives in [`../highlight_eval.py`](../highlight_eval.py).

## Run

```bash
python 15-guarded-rollout.py
```

Open http://localhost:8080/. Toggle the flag in LaunchDarkly — the page polls every 500 ms.

```bash
python 15-guarded-rollout.py --evaluate-once alice
```
