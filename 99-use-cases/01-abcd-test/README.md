# 01-abcd-test

A-B-C-D test on the navigation count label using LaunchDarkly percentage rollout.

This use case extends the [00-reference](../../00-reference/) grid navigator with a single multivariate string flag and an experiment utility that measures how often each variation is served across many user contexts.

See [application.md](application.md) for the full specification and acceptance criteria.

## How the solution works

The example has three layers that work together:

```text
┌─────────────────────────────────────────────────────────────────┐
│  Provisioning (terraform/ or rest/)                             │
│  Creates configure-navigation-count-label — OFF by default      │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Application (python-console/, node/, go/, …)                   │
│  User logs in → SDK evaluates flag for username context         │
│  Header shows {variation label}: {move count}                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Experiment (01-abcd-test-experiment.py in each language folder) │
│  1. REST API: turn flag ON + set percentage rollout             │
│  2. Run app once per trial with unique username (abcd-exp-0…)   │
│  3. Summarize observed variation distribution                   │
└─────────────────────────────────────────────────────────────────┘
```

### Flag behavior

| State | What users see |
|-------|----------------|
| Flag **off** (default after provisioning) | Always `Count: N` — the off variation |
| Flag **on** with percentage rollout | One of four labels per **unique username** context, weighted by rollout |

The four variations are string values of `configure-navigation-count-label`:

| Variation | Header line |
|-----------|-------------|
| A — `Count` | `Count: N` |
| B — `Move Count` | `Move Count: N` |
| C — `Moves` | `Moves: N` |
| D — `Navigation Counts` | `Navigation Counts: N` |

Each trial in the experiment uses a fresh username (`abcd-exp-0`, `abcd-exp-1`, …). LaunchDarkly assigns a variation deterministically per context key, so the same username always gets the same label while different usernames spread across the rollout buckets.

### Single-evaluation mode

Every application supports `--evaluate-once <username>`: evaluate the flag for that context, print the resolved label to stdout, and exit. The experiment utility invokes this mode once per trial so each run exercises the real SDK path in that language.

### Shared experiment logic

[`experiment_common.py`](experiment_common.py) at this directory’s root contains the experiment runner used by all language folders. Each folder’s `01-abcd-test-experiment.py` is a thin wrapper that points at that language’s application binary or script.

Progress prints every 10 trials: completed count, elapsed time, ETA, and running variation percentages.

## LaunchDarkly capabilities highlighted

This use case is intentionally narrow so each LaunchDarkly feature stands out:

### Multivariate string flags

[`configure-navigation-count-label`](https://launchdarkly.com/docs/sdk/features/flag-types) is a **string** flag with four variations. The server SDK’s `variation()` call returns the resolved string for the current context. This is the foundation of A/B/C/D testing — one flag key, multiple labeled outcomes.

### User contexts and deterministic assignment

Each login username becomes the LaunchDarkly **context key** (`kind: user`). Rollout assignment is stable per key: the same user always sees the same variation until targeting or rollout weights change.

### Flag on/off and off variation

After provisioning, the flag is **off** in the target environment. With the flag off, evaluation returns the **off variation** (`Count`) for every user — no rollout is applied. The interactive app demonstrates this default before you run an experiment.

### Percentage rollout (fallthrough rule)

The experiment utility uses the [REST API semantic patch](https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag) to:

1. `turnFlagOn` in the target environment
2. `updateFallthroughVariationOrRollout` with `rolloutWeights` (thousandths: 25000 = 25%)

This is LaunchDarkly’s standard pattern for splitting traffic across variations without writing custom targeting rules per user.

### Infrastructure as code and REST provisioning

- **[terraform/](terraform/)** — Terraform provider creates the flag with variations; defaults to off in `LD_ENVIRONMENT_KEY`
- **[rest/](rest/)** — Shell scripts create and inspect the flag via the REST API

Both approaches provision the same flag shape; choose based on your workflow.

### Server-side SDK evaluation

Each language implementation embeds the [server-side SDK](https://launchdarkly.com/docs/sdk/server-side) (or a Python bridge for C++ without the native SDK). Evaluation happens at request/session time in your process — not in the browser — which is appropriate for trusted backend and console apps.

## Prerequisites

```bash
export LD_PROJECT_KEY="default"
export LD_ENVIRONMENT_KEY="production"   # must match your SDK key environment
export LD_SDK_KEY="sdk-..."
export LD_API_ACCESS_TOKEN="api-..."     # experiment utility + rest/
export LD_ACCESS_TOKEN="api-..."         # terraform/
```

`LD_ENVIRONMENT_KEY` must match an environment in your project **and** the environment tied to `LD_SDK_KEY`. If the experiment reports `environment not found`, list environments with:

```bash
cd rest
source ./common.sh
api GET "/flags/${LD_PROJECT_KEY}/configure-navigation-count-label" | jq '.environments | keys'
```

## Provisioning

| Approach | Directory |
|----------|-----------|
| Terraform | [terraform/](terraform/) |
| REST API | [rest/](rest/) |

## Run an application

Pick any language folder. Example (Python console):

```bash
cd python-console
python 01-abcd-test.py
```

With the flag off, the count label is always `Count`. After running an experiment (or turning the flag on manually), distinct usernames can see different labels.

Quick single evaluation:

```bash
python 01-abcd-test.py --evaluate-once alice
```

## Run the experiment

From any language folder (after building compiled apps where required):

```bash
cd python-console   # or go/, rust/, java-console/, …
python 01-abcd-test-experiment.py
python 01-abcd-test-experiment.py --experiment-count 100 --interactive
python 01-abcd-test-experiment.py --experiment-allocation 25,25,25,25
python 01-abcd-test-experiment.py --experiment-seed 42 --experiment-salt cpp-run
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--interactive` | off | Prompt to confirm or override parameters |
| `--experiment-count` | `1000` | Number of trials |
| `--experiment-delay` | `1` | Delay between trials (ms) |
| `--experiment-allocation` | equal split | Comma-separated % per variation (must sum to 100) |
| `--experiment-seed` | random per run | Vary trial usernames between runs (`abcd-exp-{seed}-{i}`) |
| `--experiment-salt` | (none) | Extra string mixed into each trial username |

LaunchDarkly assigns variations deterministically per context key — the same usernames always yield the same distribution. By default each experiment run picks a **random seed** so results differ between runs. Pass `--experiment-seed 42` to reproduce a run.

The experiment configures rollout, runs trials, prints progress every 10 runs, then a summary table.

**Note:** Default 1000 trials spawn a fresh SDK client per subprocess call and can take a long time. Use `--experiment-count 50` for a quick check.

## Language implementations

| Language | Directory | Application type | Experiment |
|----------|-----------|------------------|------------|
| Python | [python-console/](python-console/) | Console | `01-abcd-test-experiment.py` |
| Python | [python/](python/) | Web | `01-abcd-test-experiment.py` |
| Node.js | [node-console/](node-console/) | Console | `01-abcd-test-experiment.py` |
| Node.js | [node/](node/) | Web | `01-abcd-test-experiment.py` |
| Java | [java-console/](java-console/) | Console | `01-abcd-test-experiment.py` |
| Java | [java/](java/) | Web | `01-abcd-test-experiment.py` |
| Go | [go/](go/) | Console | `01-abcd-test-experiment.py` |
| Rust | [rust/](rust/) | Console | `01-abcd-test-experiment.py` |
| C++ | [cpp/](cpp/) | Console | `01-abcd-test-experiment.py` |

Shared modules at this directory root:

| File | Purpose |
|------|---------|
| [`abcd_eval.py`](abcd_eval.py) | Python SDK evaluation (used by Python apps and C++ bridge) |
| [`abcd-eval.js`](abcd-eval.js) | Node SDK evaluation |
| [`experiment_common.py`](experiment_common.py) | REST rollout setup + trial loop + summary |

## Related examples

- [00-reference](../../00-reference/) — baseline grid navigator without flags
- [11-flag-variations](../../11-flag-variations/) — same string flag among other variation types
- [LaunchDarkly: Multivariate flags](https://launchdarkly.com/docs/sdk/features/flag-types)
- [LaunchDarkly: Percentage rollouts](https://launchdarkly.com/docs/home/flags/rollouts)
