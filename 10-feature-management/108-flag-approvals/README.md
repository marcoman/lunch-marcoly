# 108-flag-approvals

Request **approval** to turn the move-count flag on, then apply it from the grid once LaunchDarkly has approved the review.

The flag is `show-navigation-move-count-approval`. [101-flag-enablement](../101-flag-enablement/) keeps `show-navigation-move-count`.

Python web on **:8180**. Not in the series portal.

Keywords: **approvals** · **feature flags** · **required approval** · **move count**

Docs: [Approvals](https://launchdarkly.com/docs/home/releases/approvals)

## Run

See [python/README.md](python/README.md) and [application.md](application.md).

## What the page does

1. The count stays hidden while the flag is off.
2. **Request approval** sends `turnFlagOn`. It does not patch targeting.
3. Approve the request in LaunchDarkly. The page polls.
4. **Apply** turns the flag on. The next evaluation shows the count.

The page does not approve its own request. The environment's approval setting stays as it is.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| Python | [python/](python/) | Web **:8180** |
