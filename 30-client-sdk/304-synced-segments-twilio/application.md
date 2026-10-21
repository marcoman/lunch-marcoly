# Synced segments (Twilio) application specification

This document defines **34-synced-segments-twilio**. Grid, initialize,
`identify()`, and the badge flag shape match
[33-synced-segments](../33-synced-segments/application.md). The difference is
**who writes membership**.

**Causal chain:** the page calls Twilio Segment **Analytics.js**
(`identify` + `track`) → Engage Audience membership updates →
**LaunchDarkly Audiences** destination syncs included targets into a LaunchDarkly
**synced segment** → flag `show-twilio-inner-circle-badge` (`segmentMatch`)
serves `true` → client SDK **`change:`** → badge. Narrative:
[README](README.md#how-inner-circle-membership-works-twilio).

Docs: [Twilio Segment Audiences](https://launchdarkly.com/docs/home/flags/twilio) ·
[Synced segments](https://launchdarkly.com/docs/home/flags/synced-segments) ·
[@segment/analytics-next](https://www.npmjs.com/package/@segment/analytics-next)

## Overview

| Resource | Key | Role |
|----------|-----|------|
| Flag | `show-twilio-inner-circle-badge` | Boolean; **true** when the context is in the Twilio-synced segment |
| Segment | `LD_TWILIO_SEGMENT_KEY` (default `marcoly-twilio-inner-circle`) | Created by Twilio on first sync — **not** by this repo’s REST |
| Segment SDK | `@segment/analytics-next` | Browser `identify` / `track` |

The flag is **client-side available**. Fallthrough and off are `false`.
A targeting rule: **if context is in the synced segment, serve `true`**.

## Production vs 33 vs this lab

| 33 | 34 |
|----|----|
| Lab REST `included.add` on LaunchDarkly | Twilio Segment `identify` + `track` |
| Instant (same API the CDP would eventually call) | Real sync delay (first destination sync ~10 min) |
| Repo may create an unbounded/list segment | Twilio creates the synced segment |

Keywords: **Twilio Segment** · **Engage Audiences** · **synced segments** ·
**Analytics.js** · **client-side ID**

## Lab Controls

The page must not hold `LD_API_ACCESS_TOKEN`. The host proxies **flag on/off**
only. Membership buttons call Segment in the browser with `SEGMENT_WRITE_KEY`.

- **Join inner circle** — `identify(key, { innerCircle: true })` +
  `track("Joined Inner Circle")`
- **Leave inner circle** — `innerCircle: false` + `track("Left Inner Circle")`

## Acceptance criteria

1. Login initializes LaunchDarkly **and** Segment-identifies the same key
2. Badge hidden when the flag is off or the key is not in the synced segment
3. Join → after Twilio→LD sync, badge via `change:` without reload
4. Identify to a non-member → badge off; identify back to a member → badge on
5. `/api/config` never includes a server SDK key or API token (write key for
   Segment is allowed)
6. REST/Terraform create the flag with client-side availability and a
   `segmentMatch` rule; they do not create the synced segment

## Further reading

- [33-synced-segments/application.md](../33-synced-segments/application.md)
