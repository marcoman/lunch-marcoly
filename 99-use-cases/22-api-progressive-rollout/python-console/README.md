# Python (console)

Create-and-evaluate highlight flag for [22-api-progressive-rollout](../application.md).

Shared evaluation lives in [`../highlight_eval.py`](../highlight_eval.py).

## Prerequisites

- Python 3.12+ with repository virtual environment activated
- Terminal with curses support
- `LD_SDK_KEY` for the environment where the flag is provisioned

## Run

```bash
python 22-api-progressive-rollout.py
```

With the flag **off** (default after provisioning), the selected cell shows plain `X` and the header label is `(no-color)`.

Single evaluation:

```bash
python 22-api-progressive-rollout.py --evaluate-once alice
python 22-api-progressive-rollout.py --evaluate-once alice --verbose
```

The app re-evaluates every 500 ms. Start the release from the web grid or `rest/start-progressive-release.sh`. This process only reads the variation.
