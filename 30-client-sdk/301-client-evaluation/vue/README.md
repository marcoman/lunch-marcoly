# Vue

Same [301-client-evaluation](../application.md) flags, evaluated with the
[Vue SDK](https://launchdarkly.com/docs/sdk/client-side/vue)
(`launchdarkly-vue-client-sdk`). Vite injects `LD_CLIENT_SIDE_ID` and proxies lab
Controls. The page never sees `LD_SDK_KEY`.

Keywords: **Vue SDK** · **ldInit** · **useLDFlag** · **client-side ID** · **change:**

## Prerequisites

Same as [javascript/](../javascript/): Node 20, `LD_CLIENT_SIDE_ID`, provisioned
flags, REST env for Controls.

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

Open [http://127.0.0.1:8312/](http://127.0.0.1:8312/). `PORT` overrides the Vite port.

The drawer **About** tab describes this idea. **Evaluation** is the live SDK log, the context that was sent, and the latest `change` callback.

This is a different process from [javascript/](../javascript/) (** :8310 **) and
[react/](../react/) (** :8311 **). All three can run at once.

## What to expect

1. Log in. `ldInit` initializes with `{ kind: "user", key }`, and the grid mounts
   once that client reports `ready`. The lab log records `initialize` (console
   prefix `[301 evaluation][vue]`). `useLDFlag` reads `variation` once at setup, so
   a child mounted before `ready` would hold the code default until the next
   `change:` — see `src/LdSession.vue`.
   The totals read **Initialized once. Changed 0 times.**
2. Grid reads flags with `useLDFlag` — not on WASD. **Latest change** under
   Context says no streaming update yet.
3. Toggle Controls → streaming `change:` updates the grid without reload. The log
   adds one `change:` line per update, and **Latest change** shows that callback
   argument.
4. Logout then login again increments `initialize`. SDK call counts persist. A new
   login clears **Latest change** until the next stream update.
