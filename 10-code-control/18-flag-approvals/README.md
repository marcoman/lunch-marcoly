# 18-flag-approvals

**Status: stub — not implemented yet.**

Request **approval** to turn a flag on from the grid UI. Start with the
**move-count** flag. The lab environment already requires approvals; this
lesson sends a request and shows whether it is still pending.

This is not [16-percentage-rollout](../16-percentage-rollout/).

Keywords: **approvals** · **feature flags** · **required approval** ·
**move count**

Docs: [Approvals](https://launchdarkly.com/docs/home/releases/approvals)

## Intended aha

The dashboard toggle is not the only way a flag changes. The page asks for
approval to enable move count. Until that request is approved, the grid keeps
the current variation. After approval, the next evaluation shows the count.

Use a dedicated flag key so [11-flag-enablement](../11-flag-enablement/) keeps
its own count toggle.

## Direction

- One flag, one approval to turn it on.
- The screen shows the request state (pending, then approved).
- Environment approvals stay on. The lesson does not teach how to enable that
  setting.
- Not in the series portal until the app exists. Intended ports **:8180–:8183**.

## When implementing

1. `application.md` with a flag key that 11 does not use.
2. Python web first. The rail shows the approval state next to the variation.
3. REST (or the approvals API) creates the request. Do not bypass approvals
   with a direct targeting patch.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
