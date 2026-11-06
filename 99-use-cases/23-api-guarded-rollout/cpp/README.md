# C++

Console application for [23-api-guarded-rollout](../application.md).

By default, flag evaluation delegates to [`evaluate_highlight.py`](evaluate_highlight.py) (repository `.venv` Python with `launchdarkly-server-sdk`).

## Build

```bash
make
```

Optional: link the LaunchDarkly C server SDK with `LDSDK_PREFIX` set.

## Run

```bash
./23-api-guarded-rollout
./23-api-guarded-rollout --evaluate-once alice
```

Re-evaluates every 500 ms. Start the guarded release from a web grid. This process only reads the variation.
