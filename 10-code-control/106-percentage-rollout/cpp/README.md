# 16-percentage-rollout — C++ console

C++ console for a static LaunchDarkly **percentage rollout**. Flag evaluation
uses the Python server SDK helper (`evaluate_flags.py`).

Keywords: **percentage rollout** · **context key** · **sticky bucketing**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)

## Prerequisites

- A C++20 compiler
- Repository `.venv` with `launchdarkly-server-sdk`
- `LD_SDK_KEY`

## Build and run

```bash
export LD_SDK_KEY="sdk-..."
cd 10-code-control/16-percentage-rollout/cpp
make
./16-percentage-rollout
```

**N** / **P** walk generated usernames. **L** logs out. **Q** quits.
