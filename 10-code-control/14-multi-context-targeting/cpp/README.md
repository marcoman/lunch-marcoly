# C++

Console application version of the
[14-multi-context-targeting grid navigator](../application.md).

## Prerequisites

- C++20 compiler and Make
- Python **3.12+** with the repository `.venv` active or `PYTHON` set
- The LaunchDarkly flag provisioned and `LD_SDK_KEY` set

Flag evaluation delegates to [evaluate_flags.py](evaluate_flags.py), which uses
the LaunchDarkly Python server SDK and the shared `partner.evaluate_partner`
helper.

## LaunchDarkly behavior

`show-partner-org-badge` is a boolean [feature flag](https://launchdarkly.com/docs/sdk/features/flag-types)
evaluated against a [multi-context](https://launchdarkly.com/docs/home/flags/multi-contexts)
(`user` + `organization`). Org is not a user attribute.

## Build and run

```bash
make
./14-multi-context-targeting
```

The build embeds the helper path and detects the repository `.venv`; `PYTHON` or
`VIRTUAL_ENV` can override it. On the grid, `1`/`2` switch user and `3`/`4`
switch org without logging out. The flag is re-evaluated about every 500 ms.
Press `L` to log out or `Q` to quit.
