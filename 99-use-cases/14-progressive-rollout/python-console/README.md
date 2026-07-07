# Python (console)

Create-and-evaluate highlight flag for [14-progressive-rollout](../application.md).

Shared evaluation lives in [`../highlight_eval.py`](../highlight_eval.py).

## Prerequisites

- Python 3.12+ with repository virtual environment activated
- Terminal with curses support
- `LD_SDK_KEY` for the environment where the flag is provisioned

## Run

```bash
python 14-progressive-rollout.py
```

With the flag **off** (default after provisioning), the selected cell shows plain `X` and the header label is `(no-color)`.

Single evaluation:

```bash
python 14-progressive-rollout.py --evaluate-once alice
python 14-progressive-rollout.py --evaluate-once alice --verbose
```

The app re-evaluates the flag every 500 ms — toggle the flag in LaunchDarkly while the grid is open to see changes without restarting.
