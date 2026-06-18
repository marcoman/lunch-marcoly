# Python (web)

Web application for [11-flag-variations](../application.md).

## Prerequisites

- Python 3.12+ with repository virtual environment activated
- Provisioned flags and `LD_SDK_KEY`

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key |

## Build

No compile step.

## Run

```bash
python 11-flag-variations.py
```

Open http://127.0.0.1:8080/

## What to expect

Same behavior as the console app in the browser. The `/api/flags` endpoint returns `countLabel`, `luckyNumber`, `maxMoves`, and `osEmoji`.
