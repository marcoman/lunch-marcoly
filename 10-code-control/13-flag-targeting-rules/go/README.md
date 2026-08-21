# Go

Console application version of the [13-flag-targeting-rules grid navigator](../application.md).

## Prerequisites

- Go **1.22+**
- The LaunchDarkly flag provisioned and `LD_SDK_KEY` set

## LaunchDarkly behavior

`configure-team-label-style` is a string [feature flag](https://launchdarkly.com/docs/sdk/features/flag-types). The selected `team` (`red`, `blue`, or `yellow`) is a public [context attribute](https://launchdarkly.com/docs/home/flags/context-attributes) used by targeting rules. Choosing No team omits the attribute entirely, so the `plain` fallthrough applies. No private attributes are configured.

## Build and run

```bash
go mod tidy
go build -o 13-flag-targeting-rules .
./13-flag-targeting-rules
```

The flag is re-evaluated about every 500 ms. Press `L` to log out or `Q` to quit.
