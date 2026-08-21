# Python (console)

Console application for [12-flag-variations](../application.md) — string, number, JSON, and anonymous-context flags.

## Prerequisites

- Python 3.12+ with repository virtual environment activated
- Terminal with curses support
- Provisioned flags and `LD_SDK_KEY`

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |

## Flags

- `show-anonymous-host-os-emoji` — **Boolean**, evaluated with an anonymous context and private `hostOs`; gates the OS emoji.
- `configure-navigation-count-label` — **String**; supplies the always-visible move counter label.
- `configure-lucky-number` — **Number**; supplies `Lucky Number is: N`.
- `configure-max-navigation-moves` — **JSON** (`{"maxMoves": N}`); caps successful moves per session.

This is a console app; it evaluates flags but does not include the web lab or REST Controls UI.

## Build

No compile step. Dependencies from repository root `requirements.txt`.

## Run

```bash
python 12-flag-variations.py
```

Press `L` to log out or `Q` to quit.

## What to expect

1. Enter a username at the login prompt.
2. Header shows Name (optional OS emoji), positions, `{label}: N`, and `Lucky Number is: N`.
3. Flag values refresh about every 500 ms on the grid screen only.
4. Navigation stops after `maxMoves` successful moves (default 100).
