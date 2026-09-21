# 16-percentage-rollout — Python web

Static LaunchDarkly percentage rollout on the grid highlight.

## Prerequisites

- Python **3.12+** and the repository `.venv`
- `LD_SDK_KEY` for the environment provisioned by [REST](../rest/) or
  [Terraform](../terraform/)

## Run

```bash
source .venv/bin/activate
export LD_SDK_KEY="sdk-..."
cd 10-code-control/16-percentage-rollout/python
python 16-percentage-rollout.py
```

Open [http://127.0.0.1:8160/](http://127.0.0.1:8160/). `PORT` overrides the
default.

## What to expect

1. Login username becomes the LaunchDarkly `user` context key.
2. The server evaluates `enable-grid-selection-highlight-pct`.
3. `green` highlights the selected cell; `none` displays `X` only.
4. **Try next username** evaluates `<initial-name>1`, `<initial-name>2`, and so
   on without returning to login.
5. The exact-name field can evaluate any username. It does not change the
   generated sequence.
6. The eight-item history shows username, variation, and reason. Click a row to
   freshly evaluate that exact username.
7. Unique-key counts and an observed green percent sit next to the configured
   30%. Revisiting a name updates that key; it does not add a new sample.

The app contains no random-number or percentage logic for assignment; bucketing
is in LaunchDarkly. Observed percent is a classroom sample, not the rollout.

History shows the result at evaluation time. The same username is stable while
the rollout weights remain unchanged.

## Safe default

When `LD_SDK_KEY` is missing or the client is not ready, the value is `none`.
