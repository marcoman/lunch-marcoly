# React Web

Same [33-synced-segments](../application.md) flag and segment, evaluated with the
[React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web).
Vite proxies membership writes. The page never sees `LD_API_ACCESS_TOKEN`.

[Synced segments](https://launchdarkly.com/docs/home/flags/synced-segments) ·
[identify](https://launchdarkly.com/docs/sdk/features/identify)

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

Open [http://127.0.0.1:8331/](http://127.0.0.1:8331/). JavaScript is **:8330**.

## What to expect

1. Log in — `initialize`. Badge follows `show-inner-circle-badge`.
2. **Add current key** — wait for `change:`.
3. **Identify** another key — no second `initialize`; badge follows membership.
4. Log records initialize / identify / change — not WASD.
