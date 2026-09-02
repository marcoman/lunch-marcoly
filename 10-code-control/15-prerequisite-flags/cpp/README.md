# C++ (console)

Console application for [15-prerequisite-flags](../application.md). Flag
evaluation uses the Python server SDK helper (`evaluate_flags.py`) so the
unmet [prerequisite](https://launchdarkly.com/docs/home/flags/prereqs) still
surfaces as `PREREQUISITE_FAILED`.

## Prerequisites

- A C++20 compiler
- Repository `.venv` with `launchdarkly-server-sdk`
- Provisioned `-prereq` flags and `LD_SDK_KEY`

## Build and run

```bash
make
./15-prerequisite-flags
```

Login with a username. Flag changes refresh about every 500 ms. Count appears
only when the child variation is `true`. Press `L` to log out or `Q` to quit.
