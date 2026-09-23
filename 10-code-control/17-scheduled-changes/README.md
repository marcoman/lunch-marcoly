# 17-scheduled-changes

LaunchDarkly **scheduled flag changes**: the grid highlight (or theme) flips at
a selected time in the future. One visible change only.

Keywords: **scheduled changes** · **feature flags** · **targeting**

Docs: [Scheduled flag changes](https://launchdarkly.com/docs/home/flags/scheduled-changes)

Scheduled flag changes require a LaunchDarkly **Enterprise** plan.

## Intended aha

Log in, choose a delay starting at one minute, and click **Start scheduled
change**. The lab resets the flag off and replaces any pending schedule. Watch
elapsed time—not a countdown—until LaunchDarkly turns the highlight green.
The clock is in LaunchDarkly, not in the app.

A one-minute schedule typically turns green near 1:30, because LaunchDarkly
executes close to the execution date, the change has to reach the SDK stream,
and the page polls every two seconds. The second button stops the demo: it
cancels the pending change, turns the flag off, and holds the clock at its last
value.

## Do not

- Mix theme and navigation in the same schedule
- Depend on a 15-minute progressive rollout ([14](../../99-use-cases/14-progressive-rollout/))
- Use a browser timer to fake the flag change

## Implementation

| Language | Directory | Status |
|----------|-----------|--------|
| Python web | [python/](python/) | Complete · **:8170** |
| Node web | [node/](node/) | Complete · **:8171** |
| Java web | [java/](java/) | Complete · **:8172** |
| .NET web | [dotnet/](dotnet/) | Complete · **:8173** |
| Python console | [python-console/](python-console/) | Complete · **G** / **T** / **M** |
| Node console | [node-console/](node-console/) | Complete |
| Java console | [java-console/](java-console/) | Complete |
| Go console | [go/](go/) | Complete |
| Rust console | [rust/](rust/) | Complete |
| C++ console | [cpp/](cpp/) | Complete |

Provision with [REST](rest/) or [Terraform](terraform/). See
[application.md](application.md) for replacement and timing behavior.
