# 34-synced-segments-twilio

Same inner-circle **badge** as [33-synced-segments](../33-synced-segments/), but
membership is owned by **Twilio Segment**, not a LaunchDarkly REST “include this
key” call.

**Join inner circle** runs Twilio Segment **Analytics.js** (`identify` +
`track`). An Engage Audience that includes those users syncs into LaunchDarkly
through the **LaunchDarkly Audiences** destination. The flag still only asks
LaunchDarkly: *is this context in the synced segment?*

Keywords: **Twilio Segment** · **Analytics.js** · **Engage Audiences** ·
**synced segments** · **LaunchDarkly Audiences** · **identify** · **track** ·
**change:**

Docs: [syncing segments with Twilio Segment Audiences](https://launchdarkly.com/docs/home/flags/twilio) ·
[synced segments](https://launchdarkly.com/docs/home/flags/synced-segments) ·
[@segment/analytics-next](https://www.npmjs.com/package/@segment/analytics-next) ·
[identify (LaunchDarkly)](https://launchdarkly.com/docs/sdk/features/identify)

Baseline: [33-synced-segments](../33-synced-segments/).
Spec: [application.md](application.md).

## Install the Twilio Segment SDK

This is **not** `npm install twilio` (that package is Twilio’s Programmable
Messaging / Voice REST helper). Synced audiences use **Twilio Segment**
Analytics.js 2.0:

```bash
npm install @segment/analytics-next
```

Each language folder already lists that dependency. From the folder you will
run:

```bash
(cd 30-client-sdk/34-synced-segments-twilio/javascript && npm install)
(cd 30-client-sdk/34-synced-segments-twilio/react && npm install)
(cd 30-client-sdk/34-synced-segments-twilio/vue && npm install)
```

The write key is a **Segment source write key** (`SEGMENT_WRITE_KEY`). It is
safe to inject into the page the same way as `LD_CLIENT_SIDE_ID`. Do not put a
LaunchDarkly SDK key or API token in the page.

```js
import { AnalyticsBrowser } from "@segment/analytics-next";

const analytics = AnalyticsBrowser.load({ writeKey: "<SEGMENT_WRITE_KEY>" });
await analytics.identify("alice", { innerCircle: true });
await analytics.track("Joined Inner Circle", { innerCircle: true });
```

## What this demonstrates

| Piece | Key / value |
|-------|-------------|
| Flag | `show-twilio-inner-circle-badge` (boolean, client-side) |
| Segment | Twilio-created synced segment (default key `marcoly-twilio-inner-circle`; override with `LD_TWILIO_SEGMENT_KEY`) |
| Segment calls | `identify` + `track("Joined Inner Circle")` |
| UI | Badge next to Name when the flag is `true` |

**33** fakes the CDP with LaunchDarkly REST included-targets. **34** uses the
real CDP path. You need a Twilio Segment workspace with **Engage Audiences**
and the LaunchDarkly Audiences destination. First sync often takes about
**ten minutes**; later updates are often tens of seconds.

## How inner-circle membership works (Twilio)

### 1. What you set up once (outside this repo)

Follow
[Syncing segments with Twilio Segment Audiences](https://launchdarkly.com/docs/home/flags/twilio):

1. Create an Engage Audience that matches inner-circle users. For this lab,
   include people with trait `innerCircle = true` and/or event
   **Joined Inner Circle**.
2. Add the **LaunchDarkly Audiences** destination (LaunchDarkly **service
   token** with `createSegment` + `updateIncluded`, plus this environment’s
   **client-side ID**).
3. Connect that destination to the Audience. LaunchDarkly **creates the
   synced segment** (name = Audience name). Copy the **segment key** from the
   LaunchDarkly Segments page into `LD_TWILIO_SEGMENT_KEY` if it is not
   `marcoly-twilio-inner-circle`.

This lab does **not** create that segment via REST.

### 2. What the page sends to Twilio Segment

**Join inner circle** does **not** PATCH LaunchDarkly. It tells Segment:

- `identify(userId, { innerCircle: true })` — the user now has the trait
- `track("Joined Inner Circle")` — an event your Audience can also use

`userId` is the same string as the LaunchDarkly context **key** (login name).
Keep those aligned so the synced segment’s included targets match `variation`.

**Leave** sets `innerCircle: false` and tracks **Left Inner Circle**. Whether
the badge drops depends on how you defined the Audience (trait vs “ever
performed event”).

### 3. What Twilio Segment and LaunchDarkly do next

Segment evaluates the Audience. The LaunchDarkly Audiences destination
**syncs included targets** into the LaunchDarkly segment. You do not click
members onto the flag.

### 4. What the browser does

Flag `show-twilio-inner-circle-badge` has `segmentMatch` on that synced
segment. When membership arrives, the client SDK streams **`change:`** and
the badge appears. Expect a delay — this is not the instant REST path in 33.

Client-side evaluation still does **not** need Redis.

## Prerequisites

```bash
export LD_CLIENT_SIDE_ID="..."
export SEGMENT_WRITE_KEY="..."          # Twilio Segment source write key
export LD_TWILIO_SEGMENT_KEY="..."      # optional; default marcoly-twilio-inner-circle
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"
export LD_API_ACCESS_TOKEN="api-..."    # lab flag on/off + status only
```

## Provisioning

REST [`create-flags.sh`](rest/) creates **only the flag** (and the
`segmentMatch` rule). Terraform does the same. The synced **segment** must
already exist from Twilio.

## Language implementations

| Language | Directory | Run | URL |
|----------|-----------|-----|-----|
| JavaScript | [javascript/](javascript/) | `npm start` | [http://127.0.0.1:8340/](http://127.0.0.1:8340/) |
| React Web | [react/](react/) | `npm start` | [http://127.0.0.1:8341/](http://127.0.0.1:8341/) |
| Vue | [vue/](vue/) | `npm start` | [http://127.0.0.1:8342/](http://127.0.0.1:8342/) |

## Further reading

- [application.md](application.md)
- [33-synced-segments](../33-synced-segments/) — REST stand-in for the same badge
- [30-client-sdk](../README.md)
