# JavaScript (browser)

Client-side **bootstrap** for the [35-client-bootstrap](../application.md) flags.
The page passes a bootstrap map to the [JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript)
so the first paint is not the code default.
Node only serves files, injects `LD_CLIENT_SIDE_ID`, and proxies lab Controls.

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

Open [http://127.0.0.1:8350/](http://127.0.0.1:8350/). `PORT` overrides the listen port.

## What to expect

1. Log in. The SDK initializes with `{ kind: "user", key: username }`. The lab
   **SDK calls** log (and the console, prefix `[35 bootstrap]`) records
   `initialize`.
2. Flags off → `X` only, no Count (dark theme).
3. Turn on highlight / count in Controls or the dashboard; the grid updates via
   `change:` without reload. The log adds `change:` — WASD does not.
4. `/api/config` returns the client-side ID only — never the server SDK key.

React Web twin: [../react/](../react/) (** :8351 **).
Vue twin: [../vue/](../vue/) (** :8352 **).
