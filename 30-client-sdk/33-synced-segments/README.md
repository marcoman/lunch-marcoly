# 33-synced-segments

**Synced / big segment** membership from the browser: an **inner-circle badge**
when the current context is in `marcoly-inner-circle`. Lab Controls add and
remove keys through the REST API (stand-in for **Twilio Segment Audiences**).

Keywords: **synced segments** · **big segments** · **segment targeting** ·
**client-side ID** · **identify** · **change:**

Docs: [synced segments](https://launchdarkly.com/docs/home/flags/synced-segments) ·
[update big segment targets](https://launchdarkly.com/docs/api/segments/update-big-segment-targets) ·
[identify](https://launchdarkly.com/docs/sdk/features/identify) ·
[JavaScript SDK](https://launchdarkly.com/docs/sdk/client-side/javascript) ·
[React Web SDK](https://launchdarkly.com/docs/sdk/client-side/react/react-web) ·
[Vue SDK](https://launchdarkly.com/docs/sdk/client-side/vue)

Baseline: [32-client-identify](../32-client-identify/) ·
[31-client-evaluation](../31-client-evaluation/).
Spec: [application.md](application.md).

## What this demonstrates

| Piece | Key |
|-------|-----|
| Flag | `show-inner-circle-badge` (boolean, client-side) |
| Segment | `marcoly-inner-circle` |
| UI | Badge next to Name when the flag is `true` |

Production membership would be synced from Twilio Segment. This lab **injects**
test keys so you can validate targeting without that pipeline. Client-side
evaluation does **not** need Redis; that store is a **server-side** big-segment
requirement.

If the project cannot create an `unbounded` (Enterprise) segment, provisioning
falls back to a list-based segment with included keys. The flag rule is the same.

## Prerequisites

Same credentials as 31/32.

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

## Language implementations

| Language | Directory | Run | URL |
|----------|-----------|-----|-----|
| JavaScript | [javascript/](javascript/) | `npm start` | [http://127.0.0.1:8330/](http://127.0.0.1:8330/) |
| React Web | [react/](react/) | `npm start` | [http://127.0.0.1:8331/](http://127.0.0.1:8331/) |
| Vue | [vue/](vue/) | `npm start` | [http://127.0.0.1:8332/](http://127.0.0.1:8332/) |

## Further reading

- [application.md](application.md)
- [30-client-sdk](../README.md)
- [32-client-identify](../32-client-identify/)
