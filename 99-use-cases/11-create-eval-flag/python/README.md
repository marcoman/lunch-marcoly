# Python (web)

Web grid navigator for [11-create-eval-flag](../application.md).

Shared evaluation lives in [`../highlight_eval.py`](../highlight_eval.py).

## Run

```bash
python 11-create-eval-flag.py
```

Open http://localhost:8080/. Toggle the flag in LaunchDarkly — the page polls every 500 ms.

```bash
python 11-create-eval-flag.py --evaluate-once alice
```
