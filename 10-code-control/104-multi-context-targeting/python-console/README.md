# Python (console)

Console application for [104-multi-context-targeting](../application.md). It
evaluates `show-partner-org-badge` against a
[multi-context](https://launchdarkly.com/docs/home/flags/multi-contexts)
(`user` + `organization`).

## Prerequisites

- Python 3.12+ with the repository virtual environment activated
- Terminal with curses support
- Provisioned flag and `LD_SDK_KEY`

This console app evaluates the flag but has no web lab or REST Controls UI.

## Run

```bash
python 14-multi-context-targeting.py
```

Choose Alice/Bob and Acme/Globex at login. On the grid, `1`/`2` switch user and
`3`/`4` switch org without logging out. The badge refreshes about every 500 ms.
Press `L` to log out or `Q` to quit.

## Where to look

| What you see | Where it is |
|--------------|-------------|
| SDK client starts | `init_launchdarkly` |
| Poll that picks up a flag change | `run_grid` |
| User + organization context and the badge evaluation | `../partner.py` `evaluate_partner` |

Keywords: feature flags · multi-contexts · context kinds · evaluation reasons
