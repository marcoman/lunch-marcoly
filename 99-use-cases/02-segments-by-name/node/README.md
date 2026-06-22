# Node.js (web)

Web application for [02-segments-by-name](../application.md).

## Prerequisites

- Node.js **20 LTS+**
- `LD_SDK_KEY` set; provision segments + flag via [terraform](../terraform/) or [rest](../rest/)

## Build

```bash
npm install
```

## Run

```bash
node 02-segments-by-name.js
# or
npm start
```

Open http://127.0.0.1:8080/

Shared modules: [`../segment-context.js`](../segment-context.js), [`../segment-style.js`](../segment-style.js).

Single evaluation:

```bash
node 02-segments-by-name.js --evaluate-once alice
```

## What to expect

Same as [python-console/02-segments-by-name.py](../python-console/02-segments-by-name.py) in the browser:

- Light theme by default; dark theme when highlight is on
- On grid load, `/api/highlight?username=...` returns `highlightColor`, `segmentLabel`, and `segmentType`
- Header shows `Name: {username} ({segment-label})` with highlight color
- Selected cell is colored when the flag returns a color variation
