# 30-client-sdk

LaunchDarkly **client-side SDK** examples for the lunch-marcoly grid navigator.
The application runs in the browser. Evaluation uses a **client-side ID**, never
a server-side SDK key.

Baseline (no LaunchDarkly): [02-reference-client-code](../02-reference-client-code/).
Server-side flags live in [10-code-control](../10-code-control/).

| Example | Folder | What it teaches |
|---------|--------|-----------------|
| **31** | [31-client-evaluation/](31-client-evaluation/) | Initialize, **client-side availability**, `variation`, `change:` |

## Credentials

| Variable | Role |
|----------|------|
| `LD_CLIENT_SIDE_ID` | Browser SDK (same project/environment as your flags) |
| `LD_SDK_KEY` | **Not used** here — do not put it in the page |
| `LD_API_ACCESS_TOKEN` + `LD_PROJECT_KEY` + `LD_ENVIRONMENT_KEY` | Provisioning and lab Controls (local proxy only) |

Find the client-side ID in the LaunchDarkly UI: project → environment → **Client-side ID**.
It is not the value that starts with `sdk-`.

SDK credentials: [environment keys](https://launchdarkly.com/docs/home/account/environment/keys).

## Prerequisites

- Flags provisioned per example (`rest/` or `terraform/`)
- Node.js as in the [root README](../README.md)
