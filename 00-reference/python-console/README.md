# Python (console)

Console application version of the [00-reference grid navigator](../application.md).

## Prerequisites

- Python **3.12+** via [pyenv](https://github.com/pyenv/pyenv) (see [root README](../../README.md#python-and-pyenv))
- Repository virtual environment activated
- A terminal that supports curses

From the repository root:

```bash
pyenv install 3.12    # once, if needed
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment variables

None.

## Build

No compile step. Dependencies are installed from the repository root `requirements.txt` (see above).

## Run

From this directory, with pyenv and `.venv` active:

```bash
python 00-reference.py
```

Press `q` to quit the grid screen.

## What to expect

1. Enter a username at the login prompt (empty names are rejected).
2. The grid screen shows your name, current position (`m/m` initially), and previous position (`—`).
3. Use arrow keys or WASD to move; the selected cell shows **X** (no color highlight).
4. Movement stops at grid edges (no wrap-around).
