# Rust

Console application version of the [10-flag-enablement grid navigator](../application.md).

## Prerequisites

- Rust **1.75+**
- LaunchDarkly flags provisioned and `LD_SDK_KEY` set

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |

## Build

```bash
cargo build --release
```

## Run

```bash
./target/release/10-flag-enablement
```

## What to expect

Same flag behavior as [python-console/README.md](../python-console/README.md). Press `L` to log out or `Q` to quit.
