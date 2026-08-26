# 31-client-evaluation

Browser **feature flags**: initialize a client-side SDK, mark flags **client-side
available**, evaluate variations, and listen for `change:`. JavaScript uses the
JS SDK; React Web uses typed variation hooks on the same flags.

Baseline UI: [02-reference-client-code](../../02-reference-client-code/).
Behavior spec: [application.md](application.md).

Keywords: **feature flags** · **client-side ID** · **boolean variation** ·
**string variation** · **streaming `change:`** · **React Web SDK**

Docs: [JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript) ·
[React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web) ·
[environment keys](https://launchdarkly.com/docs/home/account/environment/keys) ·
[client-side availability](https://launchdarkly.com/docs/home/flags/creating-flags#make-flags-available-to-client-side-and-mobile-sdks)

## What this demonstrates

| Flag key | Off | On |
|----------|-----|-----|
| `enable-client-grid-highlight` | `none` — `X` only | Fallthrough color on the selected cell |
| `show-client-move-count` | Count hidden | `Count: N` in the header |

**Not in 31:** cohort colors from the username, host OS emoji, `identify()` without reload.

## Prerequisites

1. Same LaunchDarkly **project and environment** you already use for lunch-marcoly.
2. **`LD_CLIENT_SIDE_ID`** for that environment (not `LD_SDK_KEY`).
3. Provision the two flags (`rest/` or `terraform/`) so they are **available to
   client-side SDKs**.
4. For in-page Controls: `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, `LD_ENVIRONMENT_KEY`.

```bash
export LD_CLIENT_SIDE_ID="..."          # environment → Client-side ID
export LD_PROJECT_KEY="lunch-marcoly"   # your project key
export LD_ENVIRONMENT_KEY="production"
export LD_API_ACCESS_TOKEN="api-..."    # Controls + rest/
```

Do **not** export `LD_SDK_KEY` into the browser. The Node host never sends it to `/api/config`.

## Provisioning

| Approach | Directory |
|----------|-----------|
| REST | [rest/](rest/) |
| Terraform | [terraform/](terraform/) |

Run provisioning before opening the app.

## Language implementations

| Language | Directory | Run | URL |
|----------|-----------|-----|-----|
| JavaScript | [javascript/](javascript/) | `npm start` | [http://127.0.0.1:8310/](http://127.0.0.1:8310/) |
| React Web | [react/](react/) | `npm start` | [http://127.0.0.1:8311/](http://127.0.0.1:8311/) |

## Further reading

- [application.md](application.md)
- [30-client-sdk](../README.md)
- [32-client-identify](../32-client-identify/) — `identify()` without reload
- [33-synced-segments](../33-synced-segments/) — synced/big segment badge
- [02-reference-client-code](../../02-reference-client-code/)
