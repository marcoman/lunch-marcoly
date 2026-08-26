# React Web

Same [31-client-evaluation](../application.md) flags, evaluated with the
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

This is a different process from [javascript/](../javascript/) (** :8310 **). Both
can run at once.

## What to expect

1. Log in. `createLDReactProvider` initializes with `{ kind: "user", key }`.
   The lab log records `initialize` (console prefix `[31 evaluation][react]`).
2. Grid reads flags with `useStringVariation` / `useBoolVariation` — not on WASD.
3. Toggle Controls → streaming `change:` updates the grid without reload.
4. Logout then login again increments `initialize`. SDK call counts persist.
