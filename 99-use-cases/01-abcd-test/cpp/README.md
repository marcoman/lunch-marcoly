# C++

Console application version of the [01-abcd-test grid navigator](../application.md).

## Prerequisites

- C++20 compiler and Make
- Python **3.12+** with repository `.venv` active (default flag evaluation path)
- LaunchDarkly flag provisioned and `LD_SDK_KEY` set

Without the optional [LaunchDarkly C server SDK](https://launchdarkly.com/docs/sdk/server-side/c), flag evaluation delegates to [evaluate_label.py](evaluate_label.py) using the Python server SDK.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |

## Build

```bash
make clean && make all
```

Optional native C SDK (sets `HAS_LAUNCHDARKLY`):

```bash
make clean && LDSDK_PREFIX=/path/to/ld-sdk make all
```

## Run

From this directory (the Python helper path is baked in at build time):

```bash
source ../../../.venv/bin/activate   # or export LD_SDK_KEY and rely on repo .venv auto-detection
export LD_SDK_KEY="sdk-..."
./01-abcd-test
```

Single evaluation (used internally by the experiment):

```bash
./01-abcd-test --evaluate-once alice
```

## Run the experiment

Build the binary first, then from this directory:

```bash
python 01-abcd-test-experiment.py
python 01-abcd-test-experiment.py --experiment-count 500
python 01-abcd-test-experiment.py --interactive
python 01-abcd-test-experiment.py --experiment-seed 42
```

Trial usernames include a per-run seed (`abcd-exp-{seed}-{i}`) so repeated experiments do not produce identical distributions. LaunchDarkly rollout is deterministic per context key.

Same flag behavior as [python-console/01-abcd-test.py](../python-console/01-abcd-test.py). The header shows `{label}: N` where the label comes from `configure-navigation-count-label`. Press `L` to log out or `Q` to quit.
