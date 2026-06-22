# Go

Console application version of the [02-segments-by-name grid navigator](../application.md).

## Prerequisites

- Go **1.22+**
- LaunchDarkly segments + flag provisioned and `LD_SDK_KEY` set

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LD_SDK_KEY` | Yes | Server-side SDK key for flag evaluation |

## Build

```bash
go mod tidy
go build -o 02-segments-by-name .
```

## Run

```bash
go run .
```

## What to expect

Same flag behavior as [python-console/02-segments-by-name.py](../python-console/02-segments-by-name.py). Header shows `Name: {username} ({segment-label})` with highlight color from segment targeting. Press `L` to log out or `Q` to quit.
