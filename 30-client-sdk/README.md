# 30-client-sdk

LaunchDarkly **client-side SDK** examples for the lunch-marcoly grid navigator.
The application runs in the browser. Evaluation uses a **client-side ID**, never
a server-side SDK key. **JavaScript** (`javascript/`) uses the JS SDK.
**React Web** (`react/`, 31–34) uses the [React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web).
**Vue** (`vue/`, 31–34) uses the [Vue SDK](https://launchdarkly.com/docs/sdk/client-side/vue).

Baseline (no LaunchDarkly): [02-reference-client-code](../02-reference-client-code/).
Server-side flags live in [10-code-control](../10-code-control/).

| Example | Folder | What it teaches |
|---------|--------|-----------------|
| **31** | [31-client-evaluation/](31-client-evaluation/) | Initialize, **client-side availability**, `variation`, `change:` |
| **32** | [32-client-identify/](32-client-identify/) | **`identify()`** — switch context without reload |
| **33** | [33-synced-segments/](33-synced-segments/) | **Synced / big segment** — inner-circle badge + REST membership |
| **34** | [34-synced-segments-twilio/](34-synced-segments-twilio/) | **Twilio Segment Audiences** — same badge; `identify`/`track` then sync |

## Credentials

| Variable | Role |
|----------|------|
| `LD_CLIENT_SIDE_ID` | Browser SDK (same project/environment as your flags) |
| `LD_SDK_KEY` | **Not used** here — do not put it in the page |
| `LD_API_ACCESS_TOKEN` + `LD_PROJECT_KEY` + `LD_ENVIRONMENT_KEY` | Provisioning and lab Controls (local proxy only) |
| `SEGMENT_WRITE_KEY` | **34 only** — Twilio Segment Analytics.js write key (page-safe, like the client-side ID) |

Find the client-side ID in the LaunchDarkly UI: project → environment → **Client-side ID**.
It is not the value that starts with `sdk-`.

SDK credentials: [environment keys](https://launchdarkly.com/docs/home/account/environment/keys).

## Prerequisites

- Flags provisioned per example (`rest/` or `terraform/`)
- Node.js as in the [root README](../README.md)

## Portal

One command starts **31**–**34** for a single client SDK in a
tabbed shell: [portal/](portal/).

| Client SDK | Command | Portal | Children |
|------------|---------|--------|----------|
| JavaScript | `(cd 30-client-sdk/portal/javascript && npm start)` | **:8300** | :8310 · :8320 · :8330 · :8340 |
| React | `(cd 30-client-sdk/portal/react && npm start)` | **:8301** | :8311 · :8321 · :8331 · :8341 |
| Vue | `(cd 30-client-sdk/portal/vue && npm start)` | **:8302** | :8312 · :8322 · :8332 · :8342 |

```bash
export LD_CLIENT_SIDE_ID="..."
(cd 30-client-sdk/portal/javascript && npm start)
```

Standalone `javascript/`, `react/`, and `vue/` folders still run on their own
ports without the portal.
