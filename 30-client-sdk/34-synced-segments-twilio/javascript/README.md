# JavaScript (browser)

Inner-circle **badge** from `show-twilio-inner-circle-badge`, targeted by a
**Twilio Segment–synced** segment. The page uses the
[JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript)
and [@segment/analytics-next](https://www.npmjs.com/package/@segment/analytics-next).

[Twilio Segment Audiences](https://launchdarkly.com/docs/home/flags/twilio) ·
[parent README](../README.md#how-inner-circle-membership-works-twilio)

## Prerequisites

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

Installs LaunchDarkly JS SDK and `@segment/analytics-next` (Twilio Segment
Analytics.js). `npm start` bundles Segment with esbuild.

## Run

```bash
npm start
```

Open [http://127.0.0.1:8340/](http://127.0.0.1:8340/).

React twin: [../react/](../react/) (** :8341 **). Vue twin: [../vue/](../vue/) (** :8342 **).

## What to expect

1. Log in. LaunchDarkly **initialize** + Segment **identify** for that key.
2. **Join inner circle** — `identify` + `track("Joined Inner Circle")`. Badge
   after Twilio → LaunchDarkly sync (not instant).
3. **Identify** as another key — badge follows that key’s synced membership.
4. SDK call log records LaunchDarkly initialize / identify / change.
