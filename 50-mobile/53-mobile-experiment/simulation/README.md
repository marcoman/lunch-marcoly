# Synthetic mobile traffic

This tool uses the Python **server SDK** to generate synthetic exposure and
custom conversion events. It does not configure, allocate, or start an
experiment.

- [Python server SDK](https://launchdarkly.com/docs/sdk/server-side/python)
- [Experimentation events](https://launchdarkly.com/docs/home/experimentation/events)
- [Contexts](https://launchdarkly.com/docs/home/observability/contexts)

> **Use a dedicated environment.** Synthetic events affect experiment results.
> Never point this at an environment whose data is used for real decisions.

From the repository root, use the existing virtual environment and dependency:

```bash
source .venv/bin/activate
pip install -r requirements.txt
export LD_SDK_KEY="sdk-..." # server SDK key for the dedicated environment

python 50-mobile/53-mobile-experiment/simulation/simulate.py \
  --count 1000 \
  --seed 53 \
  --control-probability 0.30 \
  --treatment-probability 0.45 \
  --delay 0.01
```

Each stable key is `synthetic-<seed>-<index>`. Even indices use
`platform=android`; odd indices use `platform=ios`. Every user also has
`app-version` and `synthetic=true`. The tool evaluates
`acme-mobile-onboarding-v2` before probabilistically tracking
`mobile_onboarding_completed`, then flushes events before exit.

Run `python simulate.py --help` for all options. Reusing the same seed and count
reuses identities; choose a new seed for a new synthetic population.
