# segment-targeting

**Status: stub — not implemented yet.**

**Included targets** on one segment: a named list of usernames, and a flag that
serves because the current user is on that list. Add or remove the logged-in
user and the next evaluation follows.

This is the small server-side lesson to read before
[303-synced-segments](../../30-client-sdk/303-synced-segments/) and
[304-synced-segments-twilio](../../30-client-sdk/304-synced-segments-twilio/).
Big and synced segments are the same idea with membership that lives outside
the flag UI.

It has no number of its own. The numbered children in this series are
**101–109**. This folder stays under `10-code-control/` so it does not become
a 99 use case. Letter suffixes stay unused. A later number, if this lesson
gets one, comes from the `101`–`199` range.

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
