# Node.js (console)

Segment-by-name grid navigator for [02-segments-by-name](../application.md).

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

Shared modules: [`../segment-context.js`](../segment-context.js), [`../segment-style.js`](../segment-style.js).

Single evaluation:

```bash
node 02-segments-by-name.js --evaluate-once alice
```

## What to expect

Same as [python-console/02-segments-by-name.py](../python-console/02-segments-by-name.py):

- Dark console background with colored name line and selected cell when highlight is on
- Header: `Name: {username} ({segment-label})`
- Press `L` to log out or `Q` to quit
