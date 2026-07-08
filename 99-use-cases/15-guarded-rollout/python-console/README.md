# Python console — 15-guarded-rollout

Console grid navigator with **guarded rollout guardrails** when the flag serves `green`:

- Random **0–1000 ms** navigation latency
- **5%** chance of incorrect highlight color on navigation

## Run

```bash
python 15-guarded-rollout.py
```

## Headless modes

```bash
python 15-guarded-rollout.py --evaluate-once alice
python 15-guarded-rollout.py --exercise-once guard-probe-001-00
python 15-guarded-rollout.py --exercise-once guard-probe-001-00 --skip-navigation
```

See [../application.md](../application.md) and [../15-guarded-rollout-monitor.py](../15-guarded-rollout-monitor.py).
