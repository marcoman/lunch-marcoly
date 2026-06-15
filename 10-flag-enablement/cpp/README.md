# C++

Console application version of the [10-flag-enablement grid navigator](../application.md).

## Prerequisites

- C++20 compiler and Make
- Python **3.12+** with repository `.venv` active (default flag evaluation path)
- LaunchDarkly flags provisioned and `LD_SDK_KEY` set

Without the optional [LaunchDarkly C server SDK](https://launchdarkly.com/docs/sdk/server-side/c), flag evaluation delegates to [evaluate_flags.py](evaluate_flags.py) using the Python server SDK.

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
source ../../.venv/bin/activate   # or export LD_SDK_KEY and rely on repo .venv auto-detection
export LD_SDK_KEY="sdk-..."
./10-flag-enablement
```

The build embeds the path to `.venv/bin/python3` when present. You can also set `PYTHON` explicitly or activate `.venv` (`VIRTUAL_ENV`).

## What to expect

Same flag behavior as [python-console/README.md](../python-console/README.md). Press `q` to quit.
