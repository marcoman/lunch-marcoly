# JavaScript (browser)

Client SDK **`track()`** for the [36-client-track-events](../application.md)
events. The page uses the [JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript).
Node only serves files, injects `LD_CLIENT_SIDE_ID`, and proxies lab Controls.

Keywords: **track** · **custom events** · **flush** · **client-side ID**

## Prerequisites

- Node.js 20 LTS+ ([`.nvmrc`](../../../.nvmrc))
- `LD_CLIENT_SIDE_ID` for the same environment as the provisioned flags
- Flags created with **client-side availability** ([../rest/](../rest/) or [../terraform/](../terraform/))

```bash
nvm use
export LD_CLIENT_SIDE_ID="..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
export LD_API_ACCESS_TOKEN="api-..."   # Controls only
```

`LD_SDK_KEY` is **not** used. Do not put it in the page.

## Build

```bash
npm install
```

## Run

```bash
npm start
```

Open [http://127.0.0.1:8360/](http://127.0.0.1:8360/). `PORT` overrides the listen port.

## What to expect

1. Log in. The SDK initializes with `{ kind: "user", key: username }`. After
   ready, the lab **SDK calls** log (console prefix `[36 track]`) records
   `track login_completed`.
2. Move to a new cell. The log records `track grid_move` with `{ from, to }`.
   A wall bump does not.
3. Flags off → `X` only, no Count. Turn them on; the grid updates via `change:`.
4. `/api/config` returns the client-side ID only — never the server SDK key.

React Web twin: [../react/](../react/) (** :8361 **).
Vue twin: [../vue/](../vue/) (** :8362 **).
