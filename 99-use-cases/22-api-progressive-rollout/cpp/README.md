# C++

Console application for [22-api-progressive-rollout](../application.md).

By default, flag evaluation delegates to [`evaluate_highlight.py`](evaluate_highlight.py) (repository `.venv` Python with `launchdarkly-server-sdk`).

## Build

```bash
make
```

Optional: link the LaunchDarkly C server SDK with `LDSDK_PREFIX` set.

## Run

```bash
./22-api-progressive-rollout
./22-api-progressive-rollout --evaluate-once alice
```

Re-evaluates every 500 ms. Start the release from the web grid or `rest/start-progressive-release.sh`. This process only reads the variation.
