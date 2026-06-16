# Node.js (console)

Console application version of the [00-reference grid navigator](../application.md).

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

None.

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

Press `L` to log out (return to login) or `Q` to quit.

## What to expect

1. Enter a username at the login prompt (empty names are rejected).
2. The grid screen shows your name, current position (`m/m` initially), and previous position (`—`).
3. Use arrow keys or WASD to move; the selected cell shows **X** (no color highlight).
4. Movement stops at grid edges (no wrap-around).
