# segment-targeting

**Status: stub — not implemented yet.**

**Included targets** on one segment: a named list of usernames, and a flag that
serves because the current user is on that list. Add or remove the logged-in
user and the next evaluation follows.

This is the small server-side lesson to read before
[33-synced-segments](../../30-client-sdk/33-synced-segments/) and
[34-synced-segments-twilio](../../30-client-sdk/34-synced-segments-twilio/).
Big and synced segments are the same idea with membership that lives outside
the flag UI.

It has no number of its own. **18** and **19** are the last numbers in this
decade, and **20** is the AgentControl series. The folder stays under
`10-code-control/` so it does not become a 99 use case and does not take 20.
Letter suffixes (`1a`, `1b`) stay unused. If this decade has to grow, the
refactor is three digits (`101`–`199` under this series), done with the other
series, not a rename of this folder by itself.

[99-use-cases/02-segments-by-name](../../99-use-cases/02-segments-by-name/)
already matches **rule-based** segments from username attributes. This lesson
is the explicit list.

Keywords: **segments** · **included targets** · **segment targeting** ·
**feature flags**

Docs: [Segments](https://launchdarkly.com/docs/home/flags/segments)

## Intended aha

Membership is a list, not a rule on `team` or `name`. Two usernames on the
list get the targeted variation. A username that is not on the list falls
through. The screen shows the segment, whether this user is included, and the
variation.

## Direction

- One segment, one flag rule that targets it.
- Controls add and remove the current username.
- Server SDK, grid navigator. Client synced segments stay in the 30-series.
- Ports are not reserved. Do not reuse **:8180–:8183** or **:8190–:8193**.

## When implementing

1. `application.md` with a segment key and a flag key that 02, 33, and 34 do
   not use.
2. Python web first. The rail shows included / not included next to the value.
3. Point 33's README at this folder once the app exists. The link is already
   there.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
