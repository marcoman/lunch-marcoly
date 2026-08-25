# JavaScript (browser)

Inner-circle **badge** from `show-inner-circle-badge`, targeted by segment
`marcoly-inner-circle`. The page uses the
[JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript).
Node injects `LD_CLIENT_SIDE_ID` and proxies membership writes.

[Synced segments](https://launchdarkly.com/docs/home/flags/synced-segments) ·
[identify](https://launchdarkly.com/docs/sdk/features/identify)

## Prerequisites

Same as 31/32, plus the 33 flag and segment provisioned.

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

Open [http://127.0.0.1:8330/](http://127.0.0.1:8330/).

## What to expect

1. Log in. SDK **initialize**. Badge off unless that key is already in the segment.
2. **Add to inner circle** — REST add; `change:` should show the badge.
3. **Identify** as another key — badge follows that key’s membership (no second initialize).
4. **Remove from inner circle** — badge off.
5. SDK call log records initialize / identify / change — not WASD `variation`.
