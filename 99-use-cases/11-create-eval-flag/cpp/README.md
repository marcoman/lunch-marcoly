# C++

Console application for [11-create-eval-flag](../application.md).

By default, flag evaluation delegates to [`evaluate_highlight.py`](evaluate_highlight.py) (repository `.venv` Python with `launchdarkly-server-sdk`).

## Build

```bash
make
```

Optional: link the LaunchDarkly C server SDK with `LDSDK_PREFIX` set.

## Run

```bash
./11-create-eval-flag
./11-create-eval-flag --evaluate-once alice
```
