# Node.js (web)

Web application version of the [00-reference grid navigator](../application.md).

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

None — this example does not use LaunchDarkly yet.

## Build

This example has no npm dependencies. Optional install step:

```bash
npm install
```

## Run

From this directory (with the correct Node version active via `nvm use`):

```bash
node 00-reference.js
```

Or:

```bash
npm start
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/) in a browser. Press Ctrl+C to stop the server.

## What to expect

1. Enter a username on the login screen (empty names are rejected).
2. The grid screen shows your name, current position (`m/m` initially), and previous position (`—`).
3. Use arrow keys or WASD to move; the selected cell has a green background and **X**.
4. Movement stops at grid edges (no wrap-around).
