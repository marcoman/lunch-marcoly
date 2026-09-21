# 61-reference — Python web

Server-owned baseline for the observability series. Python implements the
navigator API; the browser renders returned state. No LaunchDarkly code is
present.

## Prerequisites

- Python **3.12+**
- Repository `.venv` activated (see the [series setup](../../README.md#first-time-setup))

## Environment variables

| Variable | Required | Default |
|----------|----------|---------|
| `PORT` | No | `8610` |

## Build and run

From the repository root:

```bash
source .venv/bin/activate
cd 60-observability/61-reference/python
python 61-reference.py
```

Open [http://127.0.0.1:8610/](http://127.0.0.1:8610/).

## What to expect

Login, move with arrow keys or WASD, and log out with `L`. Python keeps each
browser's grid state in a small in-memory session. Restarting the process clears
all sessions.
