# Vue

Same [36-client-track-events](../application.md) events, sent with the
[Vue SDK](https://launchdarkly.com/docs/sdk/client-side/vue)
(`launchdarkly-vue-client-sdk`). Vite injects `LD_CLIENT_SIDE_ID` and proxies lab
Controls. The page never sees `LD_SDK_KEY`.

Keywords: **track** · **custom events** · **flush** · **ldInit** ·
**client-side ID**

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

Open [http://127.0.0.1:8362/](http://127.0.0.1:8362/). `PORT` overrides the Vite port.

This is a different process from [javascript/](../javascript/) (** :8360 **) and
[react/](../react/) (** :8361 **). All three can run at once.

## What to expect

1. Log in. On `ready`, the lab log records `track login_completed` (console
   prefix `[36 track][vue]`). The grid mounts after that same `ready`.
2. Move to a new cell. The log records `track grid_move` with `{ from, to }`.
   A wall bump does not.
3. Toggle Controls → streaming `change:` updates the grid without reload.
4. Logout then login again sends `login_completed` again.
