# Vue

Same [34-synced-segments-twilio](../application.md) flag, evaluated with the
[Vue SDK](https://launchdarkly.com/docs/sdk/client-side/vue).
Join/leave uses [@segment/analytics-next](https://www.npmjs.com/package/@segment/analytics-next).

[Twilio Segment Audiences](https://launchdarkly.com/docs/home/flags/twilio) ·
[parent README](../README.md#how-inner-circle-membership-works-twilio)

## Prerequisites

Same as [javascript/](../javascript/).

```bash
nvm use
export LD_CLIENT_SIDE_ID="..."
export SEGMENT_WRITE_KEY="..."
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

Open [http://127.0.0.1:8342/](http://127.0.0.1:8342/). JavaScript is **:8340**. React is **:8341**.

## What to expect

1. Log in — LaunchDarkly `initialize` + Segment `identify`.
2. **Join inner circle** — wait for Twilio → LaunchDarkly sync, then `change:`.
3. **Identify** another key — no second LaunchDarkly `initialize`.
