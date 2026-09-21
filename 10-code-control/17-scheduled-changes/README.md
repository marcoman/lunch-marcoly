# 17-scheduled-changes

**Status: stub — not implemented yet.**

LaunchDarkly **scheduled flag changes**: the grid highlight (or theme) flips at
a time a few minutes in the future. One visible change only.

Keywords: **scheduled changes** · **feature flags** · **targeting**

Docs: [Scheduled flag changes](https://launchdarkly.com/docs/home/flags/scheduled-changes)

## Intended aha

Log in, wait past the scheduled time (no code deploy), watch the highlight
appear or disappear. The clock is in LaunchDarkly, not in the app.

## Do not

- Mix theme and navigation in the same schedule
- Depend on a 15-minute progressive rollout ([14](../../99-use-cases/14-progressive-rollout/))

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| *(none yet)* | — | Stub |
