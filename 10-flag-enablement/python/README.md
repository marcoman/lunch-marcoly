# Python (web)

Web application version of the [10-flag-enablement grid navigator](../application.md) with server-side LaunchDarkly flag evaluation.

## Prerequisites

- Python **3.12+** via [pyenv](https://github.com/pyenv/pyenv) (see [root README](../../README.md#python-and-pyenv))
- Repository virtual environment activated
- LaunchDarkly flags provisioned ([terraform/](../terraform/) or [rest/](../rest/))
- `LD_SDK_KEY` for the target environment

From the repository root:

```bash
pyenv install 3.12    # once, if needed
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |
| `LD_PROJECT_KEY` | For provisioning | Used by terraform/rest, not this app |
| `LD_ENVIRONMENT_KEY` | For provisioning | Used by terraform/rest, not this app |

```bash
export LD_SDK_KEY="sdk-..."
```

## Build

No compile step. Install dependencies from the repository root `requirements.txt`.

## Run

From this directory, with pyenv and `.venv` active:

```bash
python 10-flag-enablement.py
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/) in a browser. Press Ctrl+C to stop the server.

## What to expect

1. Enter a username on the login screen (empty names are rejected).
2. The grid matches [00-reference](../../00-reference/application.md) when both flags are off (`X` only, no count).
3. Turn on `configure-grid-selection-green-highlight` for a pink highlight on the selected cell (or enable `configure-grid-selection-context-highlight` for cohort-based colors).
4. Turn on `show-navigation-move-count` to display `Count: N` in the header (starts at 0, increments on each move).
5. Flag changes appear within ~2 seconds without navigating.
