# Go

Console application version of the [11-flag-variations grid navigator](../application.md).

## Prerequisites

- Go **1.22+**
- LaunchDarkly flags provisioned and `LD_SDK_KEY` set

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |

## Build

```bash
go mod tidy
go build -o 11-flag-variations .
```

## Run

```bash
./11-flag-variations
```

## What to expect

Same flag behavior as [python-console/11-flag-variations.py](../python-console/11-flag-variations.py). Press `L` to log out or `Q` to quit.
