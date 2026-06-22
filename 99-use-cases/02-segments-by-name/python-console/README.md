# Python (console)

Segment-by-name grid navigator for [02-segments-by-name](../application.md).

## Prerequisites

- Python 3.12+ with repository virtual environment activated
- Terminal with curses support
- `LD_SDK_KEY` set; provision segments + flag via [terraform](../terraform/) or [rest](../rest/)

## Run

```bash
python 02-segments-by-name.py
```

Shared modules: [`../segment_context.py`](../segment_context.py), [`../segment_style.py`](../segment_style.py).

## What to expect

- Dark console background when highlight is on
- Header: `Name: {username} ({segment-label})` with highlight color
- `generic` → no color; color names and human/robot/beta rules per [application.md](../application.md)
