# Python (web)

Web application version of the [11-flag-enablement grid navigator](../application.md) with server-side LaunchDarkly flag evaluation.

## Prerequisites

- Python **3.12+** via [pyenv](https://github.com/pyenv/pyenv) (see [root README](../../../README.md#python-and-pyenv))
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
| `LD_API_ACCESS_TOKEN` | For **LD lab → Controls** | REST API token (`turnFlagOn` / `turnFlagOff` / fallthrough color) |
| `LD_PROJECT_KEY` | For Controls + provisioning | Project key (e.g. `lunch-marcoly`) |
| `LD_ENVIRONMENT_KEY` | For Controls + provisioning | Environment key (e.g. `production`) |

```bash
export LD_SDK_KEY="sdk-..."
```

## Build

No compile step. Install dependencies from the repository root `requirements.txt`.

## Run

From this directory, with pyenv and `.venv` active:

```bash
python 11-flag-enablement.py
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/) in a browser. Press Ctrl+C to stop the server.

Optional: `PORT=8110` to listen on another port (used by the [series portal](../../portal/python/)).

## Portal (11 + 12)

```bash
cd ../../portal/python && python portal.py
```

Open [http://127.0.0.1:8100/](http://127.0.0.1:8100/). See [portal/python/README.md](../../portal/python/README.md).

## What to expect

1. Enter a username on the login screen (empty names are rejected).
2. The grid matches [00-reference-code](../../../00-reference-code/application.md) when both flags are off (`X` only, no count).
3. Turn on `enable-grid-selection-highlight` for a colored highlight (**string** flag: off → `none`, on → fallthrough color). Use the **Fallthrough color** dropdown in Controls to pick among existing color variations. Enable `enable-grid-highlight-color-override` for cohort-based colors from the username.
4. Turn on `show-navigation-move-count` to display `Count: N` in the header (starts at 0, increments on each move).
5. Flag changes appear within ~2 seconds without navigating.
6. After login the screen is a fixed lab layout: grid on the left, **LD lab** on the right, **Trace** across the bottom (taller / shorter / collapse).
