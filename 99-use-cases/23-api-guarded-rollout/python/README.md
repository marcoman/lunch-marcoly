# Python web — 23-api-guarded-rollout

Grid navigator for [23-api-guarded-rollout](../application.md).

The page evaluates `api-guarded-grid-highlight`. **Start guarded release** POSTs the environment release with the three guardrail metrics. The latency slider is the value sent on each move.

```bash
python 23-api-guarded-rollout.py
```

Open http://127.0.0.1:8784/ . `PORT` overrides the listen port.

```bash
python 23-api-guarded-rollout.py --evaluate-once alice
```

[Environment releases (beta)](https://launchdarkly.com/docs/api/environment-releases)
