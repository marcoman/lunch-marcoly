# Node.js (console)

ABCD test grid navigator and experiment utility for [01-abcd-test](../application.md).

## Prerequisites

- Node.js **20 LTS+**
- `LD_SDK_KEY` for the application; `LD_API_ACCESS_TOKEN` + `LD_PROJECT_KEY` + `LD_ENVIRONMENT_KEY` for experiments

## Build

```bash
npm install
npm install ..
```

The parent install provides `@launchdarkly/node-server-sdk` for shared [abcd-eval.js](../abcd-eval.js).

## Run the application

```bash
node 01-abcd-test.js
```

Single evaluation (used internally by the experiment):

```bash
node 01-abcd-test.js --evaluate-once alice
```

## Run the experiment

```bash
python 01-abcd-test-experiment.py
python 01-abcd-test-experiment.py --experiment-count 500
python 01-abcd-test-experiment.py --interactive
```

## What to expect

Same as [python-console/01-abcd-test.py](../python-console/01-abcd-test.py): 00-reference grid with `{label}: N` in the header. Press `L` to log out or `Q` to quit.
