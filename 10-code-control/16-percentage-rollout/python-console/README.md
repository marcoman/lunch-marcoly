# 16-percentage-rollout — Python console

Curses grid navigator for a static LaunchDarkly **percentage rollout**.

Keywords: **percentage rollout** · **context key** · **sticky bucketing**

Docs: [Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)

## Prerequisites

- Python **3.12+** and the repository `.venv`
- A terminal with curses support
- `LD_SDK_KEY` for the environment provisioned by [REST](../rest/) or
  [Terraform](../terraform/)

## Run

```bash
source .venv/bin/activate
export LD_SDK_KEY="sdk-..."
cd 10-code-control/16-percentage-rollout/python-console
python 16-percentage-rollout.py
```

## What to expect

1. Login username is the LaunchDarkly `user` context key.
2. The server SDK evaluates `enable-grid-selection-highlight-pct`.
3. `green` highlights the selected cell; `none` displays `X` only.
4. **N** steps forward in the generated sequence (`marco` → `marco1` →
   `marco2`) without returning to login. **P** steps back (`marco2` →
   `marco1`) and stops at the original login. That login stays the sequence
   base.
5. Header shows flag value, reason, unique-key counts, and observed green
   percent versus the configured 30%.
6. Recent evaluations (last eight) sit beside the grid. **P** is the quick
   way back to a name you already sampled.

WASD / arrows move. **L** logs out. **Q** quits. The app does not implement
bucketing; LaunchDarkly hashes flag + context kind + key.

## Safe default

When `LD_SDK_KEY` is missing or the client is not ready, the value is `none`.
