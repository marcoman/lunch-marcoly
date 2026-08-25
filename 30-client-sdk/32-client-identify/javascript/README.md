# JavaScript (browser)

**`identify()`** on the [32-client-identify](../application.md) grid.
The [JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript)
stays initialized; switching user changes the **context** only.

Identify: [changing contexts](https://launchdarkly.com/docs/sdk/features/identify).

## Prerequisites

Same as 31: Node 20, `LD_CLIENT_SIDE_ID`, provisioned 32 flags.

```bash
nvm use
export LD_CLIENT_SIDE_ID="..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
export LD_API_ACCESS_TOKEN="api-..."
```

## Build

```bash
npm install
```

## Run

```bash
npm start
```

Open [http://127.0.0.1:8320/](http://127.0.0.1:8320/). `PORT` overrides the listen port.

## What to expect

1. Log in as any name (SDK `initialize`). The lab **SDK calls** log (and the
   console, prefix `[32 identify]`) records that call.
2. Click **Alice** or **Bob** (or type a key and **Identify**). The log adds
   `identify` — not another `initialize`. Grid position and Count persist.
3. `alice` → green + Count; `bob` → blue, Count hidden; other keys → `X` only.
