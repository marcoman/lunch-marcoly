# Python (web)

Web application for [01-abcd-test](../application.md).

## Prerequisites

- Python 3.12+ with repository virtual environment activated
- `LD_SDK_KEY` for the application; `LD_API_ACCESS_TOKEN` + `LD_PROJECT_KEY` + `LD_ENVIRONMENT_KEY` for experiments

## Environment variables

| Variable | Application | Experiment |
|----------|-------------|------------|
| `LD_SDK_KEY` | Yes | Yes (via subprocess) |
| `LD_API_ACCESS_TOKEN` | No | Yes |
| `LD_PROJECT_KEY` | No | Yes |
| `LD_ENVIRONMENT_KEY` | No | Yes |

## Build

No compile step. Dependencies from repository root `requirements.txt`.

## Run the application

```bash
python 01-abcd-test.py
```

Open http://127.0.0.1:8080/

With flag **off** (default after provisioning), the count label is `Count`. Turn the flag on with percentage rollout before expecting A/B/C/D labels.

Single evaluation (used internally by the experiment):

```bash
python 01-abcd-test.py --evaluate-once alice
```

## Run the experiment

```bash
python 01-abcd-test-experiment.py
python 01-abcd-test-experiment.py --experiment-count 500
python 01-abcd-test-experiment.py --experiment-allocation 25,25,25,25
python 01-abcd-test-experiment.py --interactive
```

The experiment configures fallthrough percentage rollout, runs trials via `--evaluate-once`, and prints a summary table.

## What to expect

Same behavior as the console app in the browser. On grid load, `/api/count-label?username=...` returns `{"countLabel": "..."}` and the header shows `{label}: N` as you move.
