# 33-synced-segments

**Synced / big segment** membership from the browser: an **inner-circle badge**
when the current context is in `marcoly-inner-circle`. Lab Controls add and
remove keys through the REST API (stand-in for **Twilio Segment Audiences**).

Keywords: **synced segments** · **big segments** · **included targets** ·
**segment targeting** · **client-side ID** · **identify** · **change:**

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

If you have never used **synced segments**, the idea is: **membership lives
outside the flag**. A CDP or audience tool (here, modeled on
[Twilio Segment Audiences](https://launchdarkly.com/docs/home/flags/synced-segments))
owns *who is in the list*. LaunchDarkly **syncs** that list into a segment, and
any flag whose targeting rule is “if in this segment…” updates automatically.
You do not click users onto the flag in the dashboard.

This lab has no CDP wired up. **Add to inner circle** is the stand-in for
“Twilio Segment just added this person to the audience.” It is a LaunchDarkly
REST call that writes the same kind of **included target** a sync would write.
See [How inner-circle membership works](#how-inner-circle-membership-works).

Client-side evaluation does **not** need Redis; that store is a **server-side**
big-segment requirement.

If the project cannot create an `unbounded` (Enterprise) segment, provisioning
falls back to a list-based segment with included keys. The flag rule is the same.

## How inner-circle membership works

Read this as a causal chain, not a dashboard tour.

### 1. What LaunchDarkly already has

Provisioning created:

1. Segment **`marcoly-inner-circle`** — a bag of **user** context keys (big /
   synced-style when the plan allows).
2. Flag **`show-inner-circle-badge`** — off and fallthrough are `false`. One
   targeting rule: **if the current context is in `marcoly-inner-circle`, serve
   `true`**.

The browser SDK does **not** ask “is this key in the segment?” It asks the
flag. Segment membership is how LaunchDarkly decides that flag.

Product context:
[Segments synced from external tools](https://launchdarkly.com/docs/home/flags/synced-segments)
(keywords: **synced segments**, **included targets**, **external tool**).

### 2. The REST call that adds someone

**Add to inner circle** (Lab Controls or [`rest/add-member.sh`](rest/add-member.sh))
sends a message to LaunchDarkly: *include this user context key on the
segment.* It does **not** flip the flag, and it does **not** `identify()` the
SDK. It only changes **who is in `marcoly-inner-circle`**.

Preferred API — **update user context targets on a big segment**:
[POST `/api/v2/segments/{projectKey}/{environmentKey}/{segmentKey}/users`](https://launchdarkly.com/docs/api/segments/update-big-segment-targets)
(keywords: **big segments**, **synced segments**, **included.add**).

```http
POST /api/v2/segments/{LD_PROJECT_KEY}/{LD_ENVIRONMENT_KEY}/marcoly-inner-circle/users
Authorization: {LD_API_ACCESS_TOKEN}
Content-Type: application/json

{ "included": { "add": ["alice"] } }
```

`alice` is whatever you typed at login (or passed to `add-member.sh`). LaunchDarkly
records that **user** key as an **included target** on the segment.

From the CLI (same body, same endpoint):

```bash
(cd 30-client-sdk/33-synced-segments/rest && ./add-member.sh alice)
```

From the page, the browser POSTs `/api/segment-membership` on the local host.
The host holds `LD_API_ACCESS_TOKEN` and forwards the call above. The page never
sees the token.

If that POST is not valid for this segment (common when provisioning fell back
to a **standard list** segment), the lab retries with a
[semantic PATCH on the segment](https://launchdarkly.com/docs/api/segments/patch-segment)
instruction `addIncludedTargets` (keywords: **included targets**, **semantic
patch**). Same end state: the key is in the segment. Remove uses
`included.remove` / `removeIncludedTargets`.

In production you would not click this button. The CDP would update its
audience; LaunchDarkly would sync membership on its own (often on the order of
tens of seconds, depending on the tool). This REST write is that membership
update, compressed into one request.

### 3. What LaunchDarkly does with that message

LaunchDarkly now treats `alice` as **in** `marcoly-inner-circle`. The flag’s
`segmentMatch` rule starts serving **`true`** for that context. Other keys are
unchanged.

### 4. What the browser does next

The JS / React / Vue SDK is already initialized as that key (see **32**).
LaunchDarkly streams targeting updates. The client fires **`change:`** for
`show-inner-circle-badge`, `variation` becomes `true`, and the **inner circle**
badge appears — no reload.

Identify as a key that is **not** in the segment and the badge goes away; add
*that* key and it comes back. Membership is per context key; `identify()` only
switches whose membership you are looking at.

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
- [34-synced-segments-twilio](../34-synced-segments-twilio/) — same badge via Twilio Segment Audiences
