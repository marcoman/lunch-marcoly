# C++

Console application version of the [02-segments-by-name grid navigator](../application.md).

## Prerequisites

- C++20 compiler
- Python 3 with `launchdarkly-server-sdk` (default path when the C SDK is not linked)
- Optional: [LaunchDarkly C server SDK](https://launchdarkly.com/docs/sdk/server-side/c) via `LDSDK_PREFIX`
- LaunchDarkly segments + flag provisioned and `LD_SDK_KEY` set

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |
| `LDSDK_PREFIX` | No | Path prefix for the C server SDK (enables native evaluation) |
| `PYTHON` | No | Python executable for flag evaluation fallback |

## Build

```bash
make
```

With the C SDK:

```bash
make LDSDK_PREFIX=/path/to/ld-c-sdk
```

## Run

```bash
./02-segments-by-name
```

Without the C SDK, flag evaluation uses [`evaluate_highlight.py`](evaluate_highlight.py), which delegates to [`../segment_style.py`](../segment_style.py).

## What to expect

Same flag behavior as [python-console/02-segments-by-name.py](../python-console/02-segments-by-name.py). Header shows `Name: {username} ({segment-label})` with highlight color from segment targeting. Press `L` to log out or `Q` to quit.
