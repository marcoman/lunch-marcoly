# C++

Console application version of the [13-flag-targeting-rules grid navigator](../application.md).

## Prerequisites

- C++20 compiler and Make
- Python **3.12+** with the repository `.venv` active or `PYTHON` set
- The LaunchDarkly flag provisioned and `LD_SDK_KEY` set

Flag evaluation delegates to [evaluate_flags.py](evaluate_flags.py), which uses the LaunchDarkly Python server SDK and the shared `team_style.evaluate_team_style` helper.

## LaunchDarkly behavior

`configure-team-label-style` is a string [feature flag](https://launchdarkly.com/docs/sdk/features/flag-types). The selected `team` (`red`, `blue`, or `yellow`) is a public [context attribute](https://launchdarkly.com/docs/home/flags/context-attributes) used by targeting rules. Choosing No team omits the attribute entirely, so the `plain` fallthrough applies. No private attributes are configured.

## Build and run

```bash
make
./13-flag-targeting-rules
```

The build embeds the helper path and detects the repository `.venv`; `PYTHON` or `VIRTUAL_ENV` can override it. The flag is re-evaluated about every 500 ms. Press `L` to log out or `Q` to quit.
