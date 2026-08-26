# React Web

Same [32-client-identify](../application.md) flags, with
[`identify()`](https://launchdarkly.com/docs/sdk/features/identify) on the
[React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web).
`createLDReactProvider` runs once at login; Alice/Bob call `identify` on that client.

## Prerequisites

Same as [javascript/](../javascript/).

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

Open [http://127.0.0.1:8321/](http://127.0.0.1:8321/). JavaScript is **:8320**.

## What to expect

1. Log in — `initialize` (console prefix `[32 identify][react]`).
2. **Alice** / **Bob** — `identify` only; position and Count persist.
3. `alice` → green + Count; `bob` → blue, Count hidden.
