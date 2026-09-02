# Rust

Console application for [15-prerequisite-flags](../application.md). The Rust
server SDK evaluates parent and child flags independently so an unmet
[prerequisite](https://launchdarkly.com/docs/home/flags/prereqs) shows up as
`PREREQUISITE_FAILED`.

## Prerequisites

- Rust (stable)
- Provisioned `-prereq` flags and `LD_SDK_KEY`

## Build and run

```bash
cargo run --release
```

Login with a username. Flag changes refresh about every 500 ms. Count appears
only when the child variation is `true`. Press `L` to log out or `Q` to quit.
