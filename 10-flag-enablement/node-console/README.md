# Node.js (console)

Console application version of the [10-flag-enablement grid navigator](../application.md).

## Prerequisites

- Node.js **20 LTS+** via [nvm](https://github.com/nvm-sh/nvm)
- LaunchDarkly flags provisioned and `LD_SDK_KEY` set

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |

## Build

```bash
npm install
```

## Run

```bash
node 10-flag-enablement.js
```

## What to expect

Same flag behavior as [python-console/README.md](../python-console/README.md). Press `L` to log out or `Q` to quit.
