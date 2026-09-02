# Python (console)

Console application for [15-prerequisite-flags](../application.md). The SDK
evaluates parent and child flags independently so an unmet
[prerequisite](https://launchdarkly.com/docs/home/flags/prereqs) shows up as
`PREREQUISITE_FAILED`.

## Prerequisites

- Python 3.12+ with the repository virtual environment activated
- Terminal with curses support
- Provisioned `-prereq` flags and `LD_SDK_KEY`

This console app evaluates the flags but has no web lab or REST Controls UI.

## Run

```bash
python 15-prerequisite-flags.py
```

Login with a username. Flag changes refresh about every 500 ms. The header
shows parent/child values and evaluation reasons. Count appears only when the
child variation is `true`. Press `L` to log out or `Q` to quit.
