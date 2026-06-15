# Go

Console application version of the [00-reference grid navigator](../application.md).

## Prerequisites

- Go 1.22+

## Environment variables

None.

## Build

From this directory:

```bash
go build -o 00-reference .
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
3. Use arrow keys or WASD to move; the selected cell shows **X** (no color highlight).
4. Movement stops at grid edges (no wrap-around).
