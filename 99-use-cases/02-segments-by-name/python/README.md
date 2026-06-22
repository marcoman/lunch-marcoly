# Python (web)

Web application for [02-segments-by-name](../application.md).

## Prerequisites

- Python 3.12+ with repository virtual environment activated
- `LD_SDK_KEY` set; provision segments + flag via [terraform](../terraform/) or [rest](../rest/)

## Run

```bash
python 02-segments-by-name.py
```

Open http://127.0.0.1:8080/

Shared modules: [`../segment_context.py`](../segment_context.py), [`../segment_style.py`](../segment_style.py).

Single evaluation:

```bash
python 02-segments-by-name.py --evaluate-once alice
```

## What to expect

Same as [python-console/02-segments-by-name.py](../python-console/02-segments-by-name.py) in the browser:

- Light theme by default; dark theme when highlight is on
- On grid load, `/api/highlight?username=...` returns `highlightColor`, `segmentLabel`, and `segmentType`
- Header shows `Name: {username} ({segment-label})` with highlight color
- Selected cell is colored when the flag returns a color variation
