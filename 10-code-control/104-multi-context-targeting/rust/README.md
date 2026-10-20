# Rust

Console application version of the
[14-multi-context-targeting grid navigator](../application.md).

## Prerequisites

- Rust **1.75+**
- The LaunchDarkly flag provisioned and `LD_SDK_KEY` set

## LaunchDarkly behavior

`show-partner-org-badge` is a boolean [feature flag](https://launchdarkly.com/docs/sdk/features/flag-types)
evaluated against a [multi-context](https://launchdarkly.com/docs/home/flags/multi-contexts)
(`user` + `organization`). Org is not a user attribute.

## Build and run

```bash
cargo build --release
./target/release/14-multi-context-targeting
```

On the grid, `1`/`2` switch user and `3`/`4` switch org without logging out. The
flag is re-evaluated about every 500 ms. Press `L` to log out or `Q` to quit.
