# React Web

Same [301-client-evaluation](../application.md) flags, evaluated with the
[React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web)
(`@launchdarkly/react-sdk`). Vite injects `LD_CLIENT_SIDE_ID` and proxies lab
Controls. The page never sees `LD_SDK_KEY`.

Keywords: **React Web SDK** · **useStringVariation** · **useBoolVariation** ·
**client-side ID** · **change:**

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

Open [http://127.0.0.1:8311/](http://127.0.0.1:8311/). `PORT` overrides the Vite port.

The drawer **About** tab describes this idea. **Evaluation** is the live SDK log, the context that was sent, and the latest `change` callback.

This is a different process from [javascript/](../javascript/) (** :8310 **). Vue is
[../vue/](../vue/) (** :8312 **). All three can run at once.

## What to expect

1. Log in. `createLDReactProvider` initializes with `{ kind: "user", key }`.
   The lab log records `initialize` (console prefix `[301 evaluation][react]`).
   The totals read **Initialized once. Changed 0 times.**
2. Grid reads flags with `useStringVariation` / `useBoolVariation` — not on WASD.
   The React SDK may emit `change` with the initial flag payload, so **Latest
   change** can fill in on login. Logout clears it until the next stream update.
3. Toggle Controls, or change the highlight fallthrough color. Streaming
   `change:` updates the grid without reload. The log adds one `change:` line
   per update. **Latest change** shows the callback arguments (the context, then
   the flag keys) and the variation read after that callback. A color change
   shows `current` and, once this page has seen the flag, `previous`.
4. Logout then login again increments `initialize`. SDK call counts persist. A new
   login clears **Latest change** until the next stream update.
