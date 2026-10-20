# 17-scheduled-changes — Rust console

Rust console for LaunchDarkly **scheduled flag changes**.

Keywords: **scheduled changes** · **feature flags** · **semantic patch** · **contexts**

Docs: [Scheduled flag changes](https://launchdarkly.com/docs/home/flags/scheduled-changes)

## Prerequisites

- Rust (stable)
- A LaunchDarkly Enterprise plan
- Flag `enable-grid-selection-highlight-sched` with string variations `none` and `green`
- `LD_SDK_KEY` for evaluation
- `LD_API_ACCESS_TOKEN`, `LD_PROJECT_KEY`, and `LD_ENVIRONMENT_KEY` for **G** / **T**

## Build and run

```bash
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."
export LD_PROJECT_KEY="lunch-marcoly"
export LD_ENVIRONMENT_KEY="production"

cd 10-code-control/17-scheduled-changes/rust
cargo run --release
```

**G** replaces the pending schedule, turns the flag off, and schedules it on.
**T** cancels pending changes, turns the flag off, and freezes elapsed time.
**M** cycles 1/2/5/10 minutes; **1**/**2**/**5**/**0** select directly.
Arrows/WASD move, **L** logs out, and **Q** quits.

The clock is observational. Only SDK evaluation—not a local timer—turns the selection green.
