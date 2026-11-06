# Rust

Console application for [23-api-guarded-rollout](../application.md).

## Build

```bash
cargo build --release
```

## Run

```bash
cargo run
./target/release/23-api-guarded-rollout --evaluate-once alice
```

Re-evaluates every 500 ms. Start the guarded release from a web grid. This process only reads the variation.
