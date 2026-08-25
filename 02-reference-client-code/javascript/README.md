# JavaScript (browser)

Browser application version of the [02-reference-client-code grid navigator](../application.md). **No LaunchDarkly** — the page owns login and movement; Node only serves files.

## Prerequisites

- [nvm](https://github.com/nvm-sh/nvm) (recommended way to install and select Node.js for this repository)
- Node.js 20 LTS+ (pinned in the repository root [`.nvmrc`](../../.nvmrc))

From the repository root, before working in this folder:

```bash
nvm install
nvm use
node -v    # expect v20.x
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `8020` | HTTP listen port |

## Build

This example has no npm dependencies. Optional install step:

```bash
npm install
```

## Run

From this directory (with the correct Node version active via `nvm use`):

```bash
node 02-reference-client-code.js
```

Or:

```bash
npm start
```

Open [http://127.0.0.1:8020/](http://127.0.0.1:8020/) in a browser. Press Ctrl+C to stop the server.

## What to expect

1. Enter a username on the login screen (empty names are rejected).
2. The grid screen shows your name, current position (`m/m` initially), and previous position (`—`).
3. Use arrow keys or WASD to move; the selected cell shows **X** (no color highlight).
4. Movement stops at grid edges (no wrap-around).
5. `L` returns to login; `Q` quits (or shows a closed message if the tab cannot close).
