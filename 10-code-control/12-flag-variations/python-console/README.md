# Python (console)

Console application for [11-flag-variations](../application.md) — string, number, JSON, and anonymous-context flags.

## Prerequisites

- Python 3.12+ with repository virtual environment activated
- Terminal with curses support
- Provisioned flags and `LD_SDK_KEY`

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |

## Build

No compile step. Dependencies from repository root `requirements.txt`.

## Run

```bash
python 11-flag-variations.py
```

Press `L` to log out or `Q` to quit.

## What to expect

1. Enter a username at the login prompt.
2. Header shows Name (optional OS emoji), positions, `{label}: N`, and `Lucky Number is: N`.
3. Flag values refresh about every 500 ms on the grid screen only.
4. Navigation stops after `maxMoves` successful moves (default 100).
