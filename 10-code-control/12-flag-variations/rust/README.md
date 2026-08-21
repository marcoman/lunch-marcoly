# Rust

Console application version of the [12-flag-variations grid navigator](../application.md).

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
./target/release/12-flag-variations
```

## What to expect

Same flag behavior as [python-console/12-flag-variations.py](../python-console/12-flag-variations.py). Press `L` to log out or `Q` to quit.
