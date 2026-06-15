# Node.js (web)

Web application version of the [10-flag-enablement grid navigator](../application.md).

## Prerequisites

- Node.js **20 LTS+** via [nvm](https://github.com/nvm-sh/nvm) (see [root README](../../README.md#building-code))
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
# or
npm start
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

## What to expect

Same as [python/README.md](../python/README.md): baseline matches 00-reference when flags are off; pink/context highlight and move count are controlled by LaunchDarkly flags.
