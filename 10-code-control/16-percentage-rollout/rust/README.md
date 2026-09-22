# 16-percentage-rollout — Rust console

Rust console for a static LaunchDarkly **percentage rollout**.

Keywords: **percentage rollout** · **context key** · **sticky bucketing**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)

## Prerequisites

- Rust (stable)
- `LD_SDK_KEY`

## Build and run

```bash
export LD_SDK_KEY="sdk-..."
cd 10-code-control/16-percentage-rollout/rust
cargo run --release
```

**N** / **P** walk generated usernames. **L** logs out. **Q** quits.
