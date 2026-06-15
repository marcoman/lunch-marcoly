# C++

Console application version of the [00-reference grid navigator](../application.md).

## Prerequisites

- C++20-capable compiler
- Make

## Environment variables

None — this example does not use LaunchDarkly yet.

## Build

From this directory:

```bash
make clean
make all
```

## Run

From this directory, after a successful build:

```bash
./00-reference
```

Press `q` to quit the grid screen.

## What to expect

1. Enter a username at the login prompt (empty names are rejected).
2. The grid screen shows your name, current position (`m/m` initially), and previous position (`—`).
3. Use arrow keys or WASD to move; the selected cell has a green outline and **X**.
4. Movement stops at grid edges (no wrap-around).
