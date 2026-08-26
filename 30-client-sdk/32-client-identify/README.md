# 32-client-identify

Change the LaunchDarkly **context** in the browser with **`identify()`** — no
reload, no second `initialize`. Targeting on context **key** makes Alice vs Bob
visible on the same grid session.

Keywords: **identify** · **contexts** · **targeting rules** · **client-side ID** ·
**feature flags**

Docs: [identify](https://launchdarkly.com/docs/sdk/features/identify) ·
[target with rules](https://launchdarkly.com/docs/home/flags/target-rules) ·
[JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript) ·
[React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web) ·
[Vue SDK](https://launchdarkly.com/docs/sdk/client-side/vue)

Baseline: [31-client-evaluation](../31-client-evaluation/) ·
[02-reference-client-code](../../02-reference-client-code/).
Spec: [application.md](application.md).

## What this demonstrates

| Context key | Highlight | Count |
|-------------|-----------|-------|
| `alice` | green | shown |
| `bob` | blue | hidden |
| anyone else | `none` | hidden |

Log in as any name, then switch to `alice` / `bob` from the lab rail. Position
and Count persist; only the **context** (and flag results) change.

## Prerequisites

Same credentials as 31: `LD_CLIENT_SIDE_ID`, plus REST/token env for
provisioning and Controls.

```bash
export LD_CLIENT_SIDE_ID="..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
export LD_API_ACCESS_TOKEN="api-..."
```

## Provisioning

| Approach | Directory |
|----------|-----------|
| REST | [rest/](rest/) |
| Terraform | [terraform/](terraform/) |

Creates **new** flag keys (does not retarget 31’s flags). Flags default **on**
with Alice/Bob rules.

## Language implementations

| Language | Directory | Run | URL |
|----------|-----------|-----|-----|
| JavaScript | [javascript/](javascript/) | `npm start` | [http://127.0.0.1:8320/](http://127.0.0.1:8320/) |
| React Web | [react/](react/) | `npm start` | [http://127.0.0.1:8321/](http://127.0.0.1:8321/) |
| Vue | [vue/](vue/) | `npm start` | [http://127.0.0.1:8322/](http://127.0.0.1:8322/) |

## Further reading

- [application.md](application.md)
- [30-client-sdk](../README.md)
- [33-synced-segments](../33-synced-segments/) — synced/big segment badge
