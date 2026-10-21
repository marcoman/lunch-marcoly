# 35-client-bootstrap

Browser **bootstrap**: pass initial flag values into the client SDK so the first
paint is not the code default (`none` / count hidden) while initialization
finishes. Compared with [31-client-evaluation](../31-client-evaluation/), the
highlight is already `green` before `ready`.

Baseline UI: [02-reference-client-code](../../02-reference-client-code/).
Behavior spec: [application.md](application.md).

Keywords: **bootstrap** · **client-side SDK** · **initialize** · **variation**

Docs: [Bootstrapping](https://launchdarkly.com/docs/sdk/features/bootstrapping#javascript) ·
[JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript) ·
[React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web) ·
[Vue SDK](https://launchdarkly.com/docs/sdk/client-side/vue)

## What you should see

Log in. The lab **Paint** line starts as bootstrap (`highlight=green`, `count=true`)
before the client is ready. After `ready`, it says the stream matches — or that
the stream replaced those values if the live flags differ.

Turn the highlight flag off in Controls and reload. First paint is still green.
When the stream arrives, the cell drops to `X` only. That is the bootstrap map
losing to the live evaluation.

## Flags

| Flag key | Bootstrap | Code default |
|----------|-----------|--------------|
| `enable-client-bootstrap-highlight` | `green` | `none` |
| `show-client-bootstrap-move-count` | `true` | `false` |

Dedicated keys so 31 stays independent. Both must be available to client-side SDKs.

## Prerequisites

1. `LD_CLIENT_SIDE_ID` for the environment (not `LD_SDK_KEY`).
2. Provision the two flags ([rest/](rest/) or [terraform/](terraform/)).
3. For in-page Controls: `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, `LD_ENVIRONMENT_KEY`.

```bash
export LD_CLIENT_SIDE_ID="..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
export LD_API_ACCESS_TOKEN="api-..."
```

## Language implementations

| Language | Directory | Run | URL |
|----------|-----------|-----|-----|
| JavaScript | [javascript/](javascript/) | `npm start` | [http://127.0.0.1:8350/](http://127.0.0.1:8350/) |
| React Web | [react/](react/) | `npm start` | [http://127.0.0.1:8351/](http://127.0.0.1:8351/) |
| Vue | [vue/](vue/) | `npm start` | [http://127.0.0.1:8352/](http://127.0.0.1:8352/) |

Portal tabs: [../portal/](../portal/) (**35** on :8350 / :8351 / :8352).
