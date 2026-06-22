# Java (web)

ABCD test grid navigator and experiment utility for [01-abcd-test](../application.md).

## Prerequisites

- Java **21+**
- `LD_SDK_KEY` for the application; `LD_API_ACCESS_TOKEN` + `LD_PROJECT_KEY` + `LD_ENVIRONMENT_KEY` for experiments

## Environment variables

| Variable | Application | Experiment |
|----------|-------------|------------|
| `LD_SDK_KEY` | Yes | Yes (via subprocess) |
| `LD_API_ACCESS_TOKEN` | No | Yes |
| `LD_PROJECT_KEY` | No | Yes |
| `LD_ENVIRONMENT_KEY` | No | Yes |

## Build

```bash
./mvnw clean package
```

## Run the application

```bash
java -jar target/01-abcd-test-web.jar
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/).

With flag **off** (default after provisioning), the count label is `Count`. Turn the flag on with percentage rollout before expecting A/B/C/D labels.

Single evaluation (used internally by the experiment):

```bash
java -jar target/01-abcd-test-web.jar --evaluate-once alice
```

## Run the experiment

Build the jar first, then:

```bash
python 01-abcd-test-experiment.py
python 01-abcd-test-experiment.py --experiment-count 500
python 01-abcd-test-experiment.py --experiment-allocation 25,25,25,25
python 01-abcd-test-experiment.py --interactive
```

The experiment:

1. Sets fallthrough percentage rollout on `configure-navigation-count-label`
2. Runs `--experiment-count` trials (default 1000), each invoking the jar once with a unique username
3. Prints a summary table of variation counts

Defaults: 1000 trials, 1 ms delay, equal 25/25/25/25 allocation.

## What to expect

- Interactive app: 00-reference grid with `{label}: N` in the header
- Experiment: table of variation labels vs. observed counts
