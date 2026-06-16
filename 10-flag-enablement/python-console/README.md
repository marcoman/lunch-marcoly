# Python (console)

Console application version of the [10-flag-enablement grid navigator](../application.md) with server-side LaunchDarkly flag evaluation.

## Prerequisites

- Python **3.12+** and repository `.venv` (see [root README](../../README.md#python-and-pyenv))
- A terminal that supports curses
- LaunchDarkly flags provisioned and `LD_SDK_KEY` set

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |

```bash
export LD_SDK_KEY="sdk-..."
```

## Build

No compile step. Install dependencies from the repository root `requirements.txt`.

## Run

```bash
python 10-flag-enablement.py
```

## What to expect

1. Login with a non-empty username.
2. With both flags off, behavior matches [00-reference](../../00-reference/application.md) (`X` only, no count).
3. Enable `configure-grid-selection-green-highlight` for a colored outline on the selected cell (pink by default, or cohort colors with the context flag).
4. Enable `show-navigation-move-count` for `Count: N` in the header.
5. Flag changes refresh about every 500 ms without moving. Press `L` to log out or `Q` to quit.
