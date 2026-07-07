# C++

Console application for [04-progressive-rollout](../application.md).

By default, flag evaluation delegates to [`evaluate_highlight.py`](evaluate_highlight.py) (repository `.venv` Python with `launchdarkly-server-sdk`).

## Build

```bash
make
```

Optional: link the LaunchDarkly C server SDK with `LDSDK_PREFIX` set.

## Run

```bash
./04-progressive-rollout
./04-progressive-rollout --evaluate-once alice
```
