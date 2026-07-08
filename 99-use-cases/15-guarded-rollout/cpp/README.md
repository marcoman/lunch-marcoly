# C++

Console application for [15-guarded-rollout](../application.md).

By default, flag evaluation delegates to [`evaluate_highlight.py`](evaluate_highlight.py) (repository `.venv` Python with `launchdarkly-server-sdk`).

## Build

```bash
make
```

Optional: link the LaunchDarkly C server SDK with `LDSDK_PREFIX` set.

## Run

```bash
./15-guarded-rollout
./15-guarded-rollout --evaluate-once alice
```
