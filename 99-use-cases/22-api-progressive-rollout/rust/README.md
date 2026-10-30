# Rust

Console application for [22-api-progressive-rollout](../application.md).

## Build

```bash
cargo build --release
```

## Run

```bash
cargo run
./target/release/22-api-progressive-rollout --evaluate-once alice
```

Re-evaluates every 500 ms. Start the release from the web grid or `rest/start-progressive-release.sh`. This process only reads the variation.
