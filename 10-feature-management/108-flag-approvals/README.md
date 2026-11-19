# 108-flag-approvals

Request **approval** to turn the move-count flag on, then apply it from the grid once LaunchDarkly has approved the review.

The flag is `show-navigation-move-count-approval`. [101-flag-enablement](../101-flag-enablement/) keeps `show-navigation-move-count`.

Web on **:8180–:8183**. Not in the series portal.

Keywords: **approvals** · **feature flags** · **required approval** · **move count**

Docs: [Approvals](https://launchdarkly.com/docs/home/releases/approvals)

## Run

See [python/README.md](python/README.md), [node/README.md](node/README.md), [java/README.md](java/README.md), [dotnet/README.md](dotnet/README.md), and [application.md](application.md).

## What the page does

1. The count stays hidden while the flag is off.
2. **Request approval** sends `turnFlagOn`. The name is `Turn on the move count` plus a counter in `.request-count`, shared by all four servers. Reset does not change that counter. It does not patch targeting.
3. Approve the request in LaunchDarkly. The page polls.
4. **Apply** turns the flag on. The next evaluation shows the count.

The page does not approve its own request. The environment's approval setting stays as it is.

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| Python | [python/](python/) | Web **:8180** |
| Node | [node/](node/) | Web **:8181** |
| Java | [java/](java/) | Web **:8182** |
| .NET | [dotnet/](dotnet/) | Web **:8183** |
