# Python (console)

Console application for [13-flag-targeting-rules](../application.md), demonstrating [targeting rules](https://launchdarkly.com/docs/home/flags/target-rules) on a public `team` [context attribute](https://launchdarkly.com/docs/home/flags/context-attributes).

## Prerequisites

- Python 3.12+ with the repository virtual environment activated
- Terminal with curses and color support
- Provisioned flag and `LD_SDK_KEY`

## Flag

`configure-team-label-style` is a string feature flag. Rules serve `colored-red`, `colored-blue`, or `colored-yellow` for matching teams; No team omits the attribute and receives `plain`.

This console app evaluates the flag but has no web lab or REST Controls UI.

## Run

```bash
python 13-flag-targeting-rules.py
```

Enter a username and choose a team. The team label refreshes about every 500 ms, so dashboard targeting changes appear without logging in again. Press `L` to log out or `Q` to quit.
