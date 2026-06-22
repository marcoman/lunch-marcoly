# Rust

Console application version of the [01-abcd-test grid navigator](../application.md).

## Prerequisites

- Rust **1.75+**
- LaunchDarkly flag provisioned and `LD_SDK_KEY` set

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
cargo run --quiet --
```

Single evaluation (used internally by the experiment):

```bash
cargo run --quiet -- --evaluate-once alice
```

## Run the experiment

From this directory:

```bash
python 01-abcd-test-experiment.py
python 01-abcd-test-experiment.py --experiment-count 500
python 01-abcd-test-experiment.py --interactive
```

## What to expect

Same flag behavior as [python-console/01-abcd-test.py](../python-console/01-abcd-test.py). The header shows `{label}: N` where the label comes from `configure-navigation-count-label`. Press `L` to log out or `Q` to quit.
